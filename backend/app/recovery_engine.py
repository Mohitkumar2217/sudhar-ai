"""
The core recovery loop. In the full spec this lives inside a Temporal workflow
that sleeps between steps for days at a time. For the MVP, the same state
machine is expressed as an idempotent "tick" function: call it on a schedule
(cron, or a button in the dashboard) and it advances every invoice that's due
for action. This keeps the same guardrails (no retries on hard declines, max
4 attempts / 14 days) without needing a workflow engine running in the background.
"""
import random
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import FailedInvoice, Customer, RecoveryAction
from app.decline_taxonomy import RootCauseDiagnosticEngine, FailureDomain
from app.retry_rules import next_retry_at, is_retry_permissible
from app.llm import generate_dunning_copy
from app.email_sender import send_dunning_email


def classify_invoice(invoice: FailedInvoice, customer: Customer) -> None:
    """Runs the deterministic diagnostic engine and writes the result onto the invoice."""
    result = RootCauseDiagnosticEngine.analyze(
        raw_code=invoice.raw_decline_code,
        customer_health_score=float(customer.health_score or 1.0),
        active_days_30d=customer.days_active_past_30d or 30,
    )
    invoice.iso_8583_code = result.iso_code
    invoice.failure_type = result.failure_domain.value

    if result.failure_domain in (FailureDomain.HARD_DECLINE, FailureDomain.CHURN_SUSPECT):
        invoice.status = "DUNNING_ACTIVE"
    else:
        invoice.status = "SCHEDULED_RETRY"
        invoice.next_action_scheduled_at = next_retry_at(invoice.attempt_count)


def _log_action(db: Session, invoice: FailedInvoice, action_type: str, channel: str | None,
                 subject: str | None, body: str | None, success: bool) -> None:
    db.add(RecoveryAction(
        invoice_id=invoice.id,
        action_type=action_type,
        channel=channel,
        message_subject=subject,
        message_body=body,
        is_successful=success,
    ))


def _simulate_headless_retry(estimated_recovery_rate: float = 0.5) -> bool:
    """Stand-in for an actual gateway charge attempt. Swap for a real Stripe/Razorpay
    call when you have live credentials; the state machine around it doesn't change."""
    return random.random() < estimated_recovery_rate


def process_due_invoices(db: Session, now: datetime | None = None) -> dict:
    """Advances every invoice that's due for action. Safe to call repeatedly (idempotent
    per invoice per tick) — call this from a cron job or a 'run recovery cycle' button."""
    now = now or datetime.utcnow()
    processed = {"dunning_sent": 0, "retries_attempted": 0, "recovered": 0, "exhausted": 0}

    # New invoices that haven't been classified yet
    pending = db.query(FailedInvoice).filter(FailedInvoice.status == "PENDING").all()
    for invoice in pending:
        customer = db.query(Customer).get(invoice.customer_id)
        classify_invoice(invoice, customer)
        invoice.updated_at = now

    db.commit()

    # Hard declines / churn-suspects freshly routed to dunning
    for invoice in db.query(FailedInvoice).filter(
        FailedInvoice.status == "DUNNING_ACTIVE",
    ).all():
        already_dunned = db.query(RecoveryAction).filter(
            RecoveryAction.invoice_id == invoice.id, RecoveryAction.action_type == "DUNNING_EMAIL"
        ).first()
        if already_dunned:
            continue
        customer = db.query(Customer).get(invoice.customer_id)
        link = f"https://pay.sudhar.example/update?invoice={invoice.invoice_id}"
        copy = generate_dunning_copy(customer.name or customer.email, "your subscription", link,
                                      days_overdue=(now - invoice.created_at).days)
        sent = send_dunning_email(customer.email, copy["subject"], copy["body_text"])
        _log_action(db, invoice, "DUNNING_EMAIL", "EMAIL", copy["subject"], copy["body_text"], sent)
        processed["dunning_sent"] += 1

    # Soft declines / technical failures due for a scheduled retry
    due_retries = db.query(FailedInvoice).filter(
        FailedInvoice.status == "SCHEDULED_RETRY",
        FailedInvoice.next_action_scheduled_at <= now,
    ).all()
    for invoice in due_retries:
        days_in_recovery = (now - invoice.created_at).days
        if not is_retry_permissible(invoice.attempt_count, days_in_recovery, invoice.iso_8583_code or ""):
            invoice.status = "FAILED_EXHAUSTED"
            processed["exhausted"] += 1
            continue

        customer = db.query(Customer).get(invoice.customer_id)
        rate = RootCauseDiagnosticEngine.analyze(
            invoice.raw_decline_code, float(customer.health_score or 1.0), customer.days_active_past_30d or 30
        ).estimated_recovery_rate
        success = _simulate_headless_retry(rate)
        processed["retries_attempted"] += 1
        _log_action(db, invoice, "HEADLESS_RETRY", None, None, None, success)

        if success:
            invoice.status = "RECOVERED"
            invoice.recovered_at = now
            processed["recovered"] += 1
        else:
            invoice.attempt_count += 1
            if invoice.attempt_count >= 3:
                # Escalate to dunning alongside continued silent retries, per the original spec.
                invoice.status = "DUNNING_ACTIVE"
            else:
                invoice.next_action_scheduled_at = next_retry_at(invoice.attempt_count, now)

    db.commit()
    return processed

"""
The core recovery loop. In the full spec this lives inside a Temporal workflow
that sleeps between steps for days at a time. For the MVP, the same state
machine is expressed as an idempotent "tick" function: call it on a schedule
(cron, or a button in the dashboard) and it advances every invoice that's due
for action. This keeps the same guardrails (no retries on hard declines, max
4 attempts / 14 days) without needing a workflow engine running in the background.
"""
import os
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import FailedInvoice, Customer, Tenant, RecoveryAction
from app.decline_taxonomy import RootCauseDiagnosticEngine, FailureDomain
from app.retry_rules import next_retry_at, is_retry_permissible
from app.llm import generate_dunning_copy
from app.email_sender import send_dunning_email
from app.magic_link import generate_magic_link
from app.retry_model import predict_best_retry_delay_hours, RetryModelUnavailable
from app.fraud_heuristic import fraud_risk_score, explain_score, count_recent_failed_invoices, FRAUD_REVIEW_THRESHOLD

# Off by default. When true, retry timing comes from the trained model in
# app/retry_model.py INSTEAD of the retry_rules.py heuristic — see README Step 12
# before enabling this. The model is trained on synthetic labels, not real
# recovery outcomes, so this flag exists to demonstrate the integration point,
# not because the model is known to outperform the heuristic yet.
RETRY_MODEL_ENABLED = os.getenv("RETRY_MODEL_ENABLED", "false").lower() == "true"


def _next_retry_schedule(invoice: FailedInvoice, customer: Customer, now: datetime) -> tuple[datetime, float]:
    """Returns (next_action_scheduled_at, predicted_recovery_rate). Tries the
    trained model first if RETRY_MODEL_ENABLED; falls back to the retry_rules.py
    heuristic on ANY failure to load or predict — the recovery loop must keep
    working whether or not a model artifact exists."""
    if RETRY_MODEL_ENABLED:
        try:
            delay_hours, probability = predict_best_retry_delay_hours(
                decline_code=invoice.raw_decline_code,
                attempt_number=invoice.attempt_count,
                health_score=float(customer.health_score or 1.0),
                days_active_30d=customer.days_active_past_30d or 30,
                amount_cents=invoice.amount_due_cents,
                now=now,
            )
            return now + timedelta(hours=delay_hours), probability
        except RetryModelUnavailable:
            pass  # fall through to the heuristic below

    heuristic_rate = RootCauseDiagnosticEngine.analyze(
        invoice.raw_decline_code, float(customer.health_score or 1.0), customer.days_active_past_30d or 30
    ).estimated_recovery_rate
    return next_retry_at(invoice.attempt_count, now), heuristic_rate


def classify_invoice(db: Session, invoice: FailedInvoice, customer: Customer, now: datetime | None = None) -> None:
    """Runs the fraud check first, then the deterministic diagnostic engine.
    A flagged invoice never reaches retry or dunning — it's routed to
    FRAUD_REVIEW and held for a human, since neither silently retrying nor
    emailing a card-testing target is the right move."""
    now = now or datetime.utcnow()

    recent_count = count_recent_failed_invoices(db, customer.id, now)
    risk = fraud_risk_score(invoice, customer, recent_count)
    if risk >= FRAUD_REVIEW_THRESHOLD:
        invoice.status = "FRAUD_REVIEW"
        invoice.failure_type = "SUSPECTED_FRAUD"
        reasons = "; ".join(explain_score(invoice, customer, recent_count)) or "Heuristic threshold exceeded"
        _log_action(
            db, invoice, "FRAUD_FLAGGED", None, None, reasons, success=None,
            attempt_number=invoice.attempt_count, decline_code=invoice.raw_decline_code,
            health_score=float(customer.health_score or 1.0),
        )
        return

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
        invoice.next_action_scheduled_at, _ = _next_retry_schedule(invoice, customer, now)


def _log_action(db: Session, invoice: FailedInvoice, action_type: str, channel: str | None,
                 subject: str | None, body: str | None, success: bool | None,
                 attempt_number: int | None = None, decline_code: str | None = None,
                 health_score: float | None = None) -> None:
    db.add(RecoveryAction(
        invoice_id=invoice.id,
        action_type=action_type,
        channel=channel,
        message_subject=subject,
        message_body=body,
        is_successful=success,
        attempt_number=attempt_number,
        decline_code_snapshot=decline_code,
        health_score_snapshot=health_score,
    ))


def _simulate_headless_retry(estimated_recovery_rate: float = 0.5) -> bool:
    """Stand-in for an actual gateway charge attempt. Swap for a real Stripe/Razorpay
    call when you have live credentials; the state machine around it doesn't change."""
    return random.random() < estimated_recovery_rate


def process_due_invoices(db: Session, now: datetime | None = None) -> dict:
    """Advances every invoice that's due for action. Safe to call repeatedly (idempotent
    per invoice per tick) — call this from a cron job or a 'run recovery cycle' button."""
    now = now or datetime.utcnow()
    processed = {"dunning_sent": 0, "retries_attempted": 0, "recovered": 0, "exhausted": 0, "fraud_flagged": 0}

    # New invoices that haven't been classified yet
    pending = db.query(FailedInvoice).filter(FailedInvoice.status == "PENDING").all()
    for invoice in pending:
        customer = db.query(Customer).get(invoice.customer_id)
        classify_invoice(db, invoice, customer, now)
        if invoice.status == "FRAUD_REVIEW":
            processed["fraud_flagged"] += 1
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
        tenant = db.query(Tenant).get(invoice.tenant_id)
        link = generate_magic_link(invoice.tenant_id, customer.id, invoice.id)
        copy = generate_dunning_copy(customer.name or customer.email, tenant.name, link,
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
        _, rate = _next_retry_schedule(invoice, customer, now)
        success = _simulate_headless_retry(rate)
        processed["retries_attempted"] += 1
        # Snapshot attempt_count/decline_code/health_score NOW — invoice.attempt_count
        # is about to be incremented below on failure, and health_score could drift
        # later in a real deployment. Training data must reflect state AT this attempt.
        _log_action(
            db, invoice, "HEADLESS_RETRY", None, None, None, success,
            attempt_number=invoice.attempt_count,
            decline_code=invoice.raw_decline_code,
            health_score=float(customer.health_score or 1.0),
        )

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
                invoice.next_action_scheduled_at, _ = _next_retry_schedule(invoice, customer, now)

    db.commit()
    return processed

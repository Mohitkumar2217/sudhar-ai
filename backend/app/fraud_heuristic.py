"""
Fraud-risk scoring for Sudhar AI's own invoices — the piece that actually
integrates with the recovery engine, unlike scripts/train_fraud_demo_model.py.

This is an explicit, auditable heuristic, not a trained model. That's a
deliberate choice, not a shortcut: no labeled fraud data exists for Sudhar AI's
own transactions (the real fraud data available — creditcard.csv — uses an
unrelated, PCA-anonymized feature space that can't be computed for a
FailedInvoice; see train_fraud_demo_model.py's docstring for the full
reasoning). Training a model on invented labels here would repeat the exact
mistake called out in the retry-timing model's README section — a model can't
be smarter than the labels it's trained on, and here there are no real ones
yet. A transparent point-based rule is more honest than a model dressed up to
look more rigorous than it is.

The specific pattern this targets — card testing — shows up as several
distinct failed charges from the same customer in a short window, often for
unusually large amounts from an account with almost no history. Legitimate
retry activity looks nothing like this: retry_rules.py enforces 24h+ between
attempts on the SAME invoice, so rapid activity across DIFFERENT invoices for
the same customer is the actual anomalous signal, not attempt frequency on one
invoice.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import FailedInvoice, Customer

# Weights are illustrative starting points, not calibrated against real fraud
# outcomes (none exist yet for Sudhar AI's own data) — treat as a starting
# configuration to tune once real flagged/confirmed cases accumulate.
WEIGHT_NEW_CUSTOMER_HIGH_AMOUNT = 0.35
WEIGHT_VELOCITY = 0.45
WEIGHT_LOW_ENGAGEMENT = 0.20

NEW_CUSTOMER_DAYS_ACTIVE_THRESHOLD = 1
HIGH_AMOUNT_CENTS_THRESHOLD = 50000  # $500
VELOCITY_LOOKBACK_HOURS = 1
VELOCITY_COUNT_THRESHOLD = 3  # 3+ distinct failed invoices from one customer within the lookback window
LOW_HEALTH_SCORE_THRESHOLD = 0.10

FRAUD_REVIEW_THRESHOLD = 0.6


def count_recent_failed_invoices(db: Session, customer_id: str, now: datetime) -> int:
    cutoff = now - timedelta(hours=VELOCITY_LOOKBACK_HOURS)
    return (
        db.query(FailedInvoice)
        .filter(FailedInvoice.customer_id == customer_id, FailedInvoice.created_at >= cutoff)
        .count()
    )


def fraud_risk_score(
    invoice: FailedInvoice,
    customer: Customer,
    recent_failed_invoice_count: int,
) -> float:
    """Returns a 0.0-1.0 score. Each contributing rule is independent and
    additive, capped at 1.0 — this is intentionally simple enough that any
    flagged invoice's score can be explained in one sentence, which matters
    more than marginal accuracy for a review queue a human will act on."""
    score = 0.0

    if (customer.days_active_past_30d or 0) <= NEW_CUSTOMER_DAYS_ACTIVE_THRESHOLD \
            and invoice.amount_due_cents >= HIGH_AMOUNT_CENTS_THRESHOLD:
        score += WEIGHT_NEW_CUSTOMER_HIGH_AMOUNT

    if recent_failed_invoice_count >= VELOCITY_COUNT_THRESHOLD:
        score += WEIGHT_VELOCITY

    if float(customer.health_score or 1.0) < LOW_HEALTH_SCORE_THRESHOLD:
        score += WEIGHT_LOW_ENGAGEMENT

    return min(score, 1.0)


def explain_score(invoice: FailedInvoice, customer: Customer, recent_failed_invoice_count: int) -> list[str]:
    """Human-readable reasons behind a score, for the review queue — a fraud
    flag a reviewer can't understand is a fraud flag they'll learn to ignore."""
    reasons = []
    if (customer.days_active_past_30d or 0) <= NEW_CUSTOMER_DAYS_ACTIVE_THRESHOLD \
            and invoice.amount_due_cents >= HIGH_AMOUNT_CENTS_THRESHOLD:
        reasons.append(f"New customer (\u2264{NEW_CUSTOMER_DAYS_ACTIVE_THRESHOLD}d active) with a high-value charge")
    if recent_failed_invoice_count >= VELOCITY_COUNT_THRESHOLD:
        reasons.append(f"{recent_failed_invoice_count} failed charges from this customer in the last {VELOCITY_LOOKBACK_HOURS}h")
    if float(customer.health_score or 1.0) < LOW_HEALTH_SCORE_THRESHOLD:
        reasons.append("Very low engagement score")
    return reasons

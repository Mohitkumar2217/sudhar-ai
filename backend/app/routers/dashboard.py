from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FailedInvoice, RecoveryAction

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ACTIVE_STATUSES = ("PENDING", "SCHEDULED_RETRY", "DUNNING_ACTIVE")


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    at_risk_cents = db.query(func.coalesce(func.sum(FailedInvoice.amount_due_cents), 0)).filter(
        FailedInvoice.status.in_(ACTIVE_STATUSES)
    ).scalar()

    recovered_cents = db.query(func.coalesce(func.sum(FailedInvoice.amount_due_cents), 0)).filter(
        FailedInvoice.status == "RECOVERED"
    ).scalar()

    exhausted_cents = db.query(func.coalesce(func.sum(FailedInvoice.amount_due_cents), 0)).filter(
        FailedInvoice.status == "FAILED_EXHAUSTED"
    ).scalar()

    total_resolved = recovered_cents + exhausted_cents
    recovery_rate = round(recovered_cents / total_resolved, 4) if total_resolved else None

    top_failure_reasons = (
        db.query(FailedInvoice.raw_decline_code, func.count(FailedInvoice.id).label("count"))
        .group_by(FailedInvoice.raw_decline_code)
        .order_by(func.count(FailedInvoice.id).desc())
        .limit(5)
        .all()
    )

    recent_actions = (
        db.query(RecoveryAction).order_by(RecoveryAction.created_at.desc()).limit(10).all()
    )

    return {
        "revenue_at_risk_cents": at_risk_cents,
        "revenue_recovered_cents": recovered_cents,
        "revenue_exhausted_cents": exhausted_cents,
        "recovery_rate": recovery_rate,
        "top_failure_reasons": [{"reason": r, "count": c} for r, c in top_failure_reasons],
        "recent_actions": [
            {
                "invoice_id": a.invoice_id,
                "action_type": a.action_type,
                "channel": a.channel,
                "is_successful": a.is_successful,
                "created_at": a.created_at,
            }
            for a in recent_actions
        ],
    }

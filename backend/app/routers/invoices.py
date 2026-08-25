from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FailedInvoice, Customer, RecoveryAction
from app.recovery_engine import process_due_invoices

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _serialize(invoice: FailedInvoice, customer: Customer) -> dict:
    return {
        "id": invoice.id,
        "invoice_id": invoice.invoice_id,
        "customer_name": customer.name,
        "customer_email": customer.email,
        "amount_due_cents": invoice.amount_due_cents,
        "raw_decline_code": invoice.raw_decline_code,
        "iso_8583_code": invoice.iso_8583_code,
        "failure_type": invoice.failure_type,
        "status": invoice.status,
        "attempt_count": invoice.attempt_count,
        "next_action_scheduled_at": invoice.next_action_scheduled_at,
        "recovered_at": invoice.recovered_at,
        "created_at": invoice.created_at,
    }


@router.get("")
def list_invoices(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(FailedInvoice)
    if status:
        query = query.filter(FailedInvoice.status == status)
    invoices = query.order_by(FailedInvoice.created_at.desc()).limit(200).all()
    out = []
    for inv in invoices:
        customer = db.query(Customer).get(inv.customer_id)
        out.append(_serialize(inv, customer))
    return out


@router.post("/run-recovery-cycle")
def run_recovery_cycle(db: Session = Depends(get_db)):
    """Advances every invoice that's due for action right now. In production this
    would be triggered by a cron job every few minutes instead of a manual call."""
    result = process_due_invoices(db, now=datetime.utcnow())
    return {"ran_at": datetime.utcnow(), "result": result}


@router.get("/actions")
def list_actions(limit: int = 30, db: Session = Depends(get_db)):
    """A dedicated feed endpoint, richer than the top-10 embedded in
    /dashboard/summary — includes the customer and invoice context so the
    frontend can render a real activity log instead of a bare action list."""
    actions = (
        db.query(RecoveryAction)
        .order_by(RecoveryAction.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    out = []
    for a in actions:
        invoice = db.query(FailedInvoice).get(a.invoice_id)
        customer = db.query(Customer).get(invoice.customer_id) if invoice else None
        out.append({
            "id": a.id,
            "action_type": a.action_type,
            "channel": a.channel,
            "is_successful": a.is_successful,
            "created_at": a.created_at,
            "invoice_ref": invoice.invoice_id if invoice else None,
            "customer_name": (customer.name or customer.email) if customer else None,
            "amount_due_cents": invoice.amount_due_cents if invoice else None,
        })
    return out

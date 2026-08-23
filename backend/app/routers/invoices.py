from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FailedInvoice, Customer
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

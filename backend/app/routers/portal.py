"""
Backend for the zero-auth "update your payment method" portal. The token itself
is the auth — no login, no password, scoped to one invoice, expires in 15 minutes.

PCI-DSS note: this endpoint never receives raw card data. In a real deployment,
the frontend would embed Stripe's Payment Element (or the equivalent for your
gateway), which tokenizes the card entirely client-side — this backend would only
ever see a gateway-issued token, keeping it out of PCI scope (SAQ-A). The MVP
"update card" action below is a simulated confirmation step for exactly that
reason: there's no real card form to wire up without a live Stripe account, and
building a fake one that *looks* like it collects card data would be actively
misleading about what this code does.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import SessionLocal
from app.models import FailedInvoice, Customer, Tenant, RecoveryAction
from app.magic_link import decode_magic_link, MagicLinkError

router = APIRouter(prefix="/portal", tags=["portal"])


class TokenBody(BaseModel):
    token: str


def _resolve_invoice(db, token: str) -> FailedInvoice:
    try:
        payload = decode_magic_link(token)
    except MagicLinkError as e:
        raise HTTPException(status_code=401, detail=str(e))

    invoice = (
        db.query(FailedInvoice)
        .filter(
            FailedInvoice.id == payload["invoice_id"],
            FailedInvoice.tenant_id == payload["tenant_id"],
        )
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice


@router.get("/invoice")
def get_invoice_for_token(token: str):
    db = SessionLocal()
    try:
        invoice = _resolve_invoice(db, token)
        tenant = db.query(Tenant).get(invoice.tenant_id)
        customer = db.query(Customer).get(invoice.customer_id)

        if invoice.status == "RECOVERED":
            return {"already_recovered": True, "tenant_name": tenant.name}

        return {
            "already_recovered": False,
            "tenant_name": tenant.name,
            "customer_name": customer.name or customer.email,
            "amount_due_cents": invoice.amount_due_cents,
            "currency": invoice.currency,
            "invoice_ref": invoice.invoice_id,
        }
    finally:
        db.close()


@router.post("/update-card")
def update_card(body: TokenBody):
    db = SessionLocal()
    try:
        invoice = _resolve_invoice(db, body.token)
        if invoice.status == "RECOVERED":
            return {"status": "already_recovered"}

        invoice.status = "RECOVERED"
        invoice.recovered_at = datetime.utcnow()
        db.add(RecoveryAction(
            invoice_id=invoice.id,
            action_type="CARD_UPDATED",
            channel="PORTAL",
            is_successful=True,
        ))
        db.commit()
        return {"status": "recovered"}
    finally:
        db.close()

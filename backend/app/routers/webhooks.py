"""
Real Stripe webhook ingestion, replacing the seed script as the path for getting
failed-payment events into the system. Handles `charge.failed` and
`invoice.payment_failed` events; auto-creates the customer record on first sight
since Stripe doesn't carry the engagement/health signals this app scores on —
those get backfilled from a separate telemetry source in a real deployment.
"""
import os
import json
from datetime import datetime

from fastapi import APIRouter, Request, Header, HTTPException
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Tenant, Customer, FailedInvoice
from app.webhook_models import WebhookEvent
from app.stripe_signature import verify_stripe_signature, SignatureVerificationError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_local_dev_secret")

HANDLED_EVENT_TYPES = {"charge.failed", "invoice.payment_failed"}


def _extract_failure_fields(event_type: str, obj: dict) -> dict:
    """Normalizes the two event shapes we handle into one internal representation.
    Real Stripe payloads for invoice.payment_failed nest the charge failure under
    the associated charge; for charge.failed the failure fields are top-level."""
    if event_type == "charge.failed":
        return {
            "invoice_id": obj["id"],  # charge id, e.g. ch_...
            "amount_due_cents": obj.get("amount", 0),
            "currency": obj.get("currency", "usd").upper(),
            "external_customer_id": obj.get("customer") or "unknown_customer",
            "raw_decline_code": obj.get("failure_code") or obj.get("outcome", {}).get("reason") or "generic_decline",
        }
    # invoice.payment_failed
    return {
        "invoice_id": obj["id"],  # invoice id, e.g. in_...
        "amount_due_cents": obj.get("amount_due", 0),
        "currency": obj.get("currency", "usd").upper(),
        "external_customer_id": obj.get("customer") or "unknown_customer",
        "raw_decline_code": (obj.get("last_finalization_error") or {}).get("decline_code", "generic_decline"),
    }


@router.post("/stripe/{tenant_id}")
async def receive_stripe_webhook(
    tenant_id: str,
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
):
    raw_body = await request.body()

    try:
        verify_stripe_signature(raw_body, stripe_signature or "", STRIPE_WEBHOOK_SECRET)
    except SignatureVerificationError as e:
        raise HTTPException(status_code=401, detail=str(e))

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event_id = event.get("id")
    event_type = event.get("type")
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Payload missing 'id' or 'type'.")

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail=f"Unknown tenant_id: {tenant_id}")

        # Idempotency: Stripe redelivers webhooks on any non-2xx response, so a
        # duplicate event_id is expected traffic, not an error.
        if db.query(WebhookEvent).get(event_id):
            return {"status": "ignored", "reason": "duplicate_event"}
        db.add(WebhookEvent(id=event_id, tenant_id=tenant_id, event_type=event_type))

        if event_type not in HANDLED_EVENT_TYPES:
            db.commit()
            return {"status": "ignored", "reason": f"unhandled_event_type:{event_type}"}

        obj = event.get("data", {}).get("object", {})
        fields = _extract_failure_fields(event_type, obj)

        customer = (
            db.query(Customer)
            .filter(Customer.tenant_id == tenant_id, Customer.external_customer_id == fields["external_customer_id"])
            .first()
        )
        if not customer:
            customer = Customer(
                tenant_id=tenant_id,
                external_customer_id=fields["external_customer_id"],
                email=obj.get("receipt_email") or obj.get("customer_email") or "unknown@example.com",
                name=obj.get("billing_details", {}).get("name") if isinstance(obj.get("billing_details"), dict) else None,
                mrr_cents=fields["amount_due_cents"],
                # Stripe doesn't carry engagement data — defaults here, backfilled
                # from your product telemetry (Segment/Mixpanel/etc) in production.
                health_score=1.0,
                days_active_past_30d=30,
            )
            db.add(customer)
            db.flush()  # get customer.id without a full commit

        invoice = FailedInvoice(
            tenant_id=tenant_id,
            customer_id=customer.id,
            invoice_id=fields["invoice_id"],
            amount_due_cents=fields["amount_due_cents"],
            currency=fields["currency"],
            raw_decline_code=fields["raw_decline_code"],
            failure_type="SOFT_DECLINE",  # placeholder — set for real on the next recovery cycle tick
            status="PENDING",
            attempt_count=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(invoice)
        db.commit()

        return {"status": "enqueued", "event_id": event_id, "invoice_id": fields["invoice_id"]}

    except IntegrityError:
        db.rollback()
        return {"status": "ignored", "reason": "duplicate_invoice"}
    finally:
        db.close()

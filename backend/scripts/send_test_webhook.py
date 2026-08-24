"""
Sends a realistically-shaped, correctly-signed charge.failed webhook to the local
server. Stripe's real webhooks aren't reachable from every dev environment (or in
this project's sandboxed build/test environment at all), so this script exists to
exercise the exact same signature-verification and idempotency code paths that a
real Stripe delivery would hit — it's not a mock of the endpoint, it's a real
signed HTTP request against it.

Usage:
    python -m scripts.send_test_webhook <tenant_id> [decline_code]
    python -m scripts.send_test_webhook <tenant_id> insufficient_funds
"""
import json
import os
import sys
import time
import uuid

import requests

from app.stripe_signature import sign_payload

WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_local_dev_secret")
BASE_URL = os.getenv("SUDHAR_API_URL", "http://127.0.0.1:8000")


def build_charge_failed_event(decline_code: str) -> dict:
    return {
        "id": f"evt_{uuid.uuid4().hex[:24]}",
        "type": "charge.failed",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": f"ch_{uuid.uuid4().hex[:24]}",
                "amount": 4900,
                "currency": "usd",
                "customer": f"cus_test_{uuid.uuid4().hex[:8]}",
                "failure_code": decline_code,
                "receipt_email": "webhook.test@example.com",
                "billing_details": {"name": "Webhook Test Customer"},
            }
        },
    }


def send(tenant_id: str, decline_code: str = "insufficient_funds", corrupt_signature: bool = False):
    event = build_charge_failed_event(decline_code)
    payload = json.dumps(event).encode("utf-8")
    sig = sign_payload(payload, WEBHOOK_SECRET)
    if corrupt_signature:
        sig = sig[:-4] + "0000"

    resp = requests.post(
        f"{BASE_URL}/webhooks/stripe/{tenant_id}",
        data=payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig},
    )
    print(f"[{resp.status_code}] {resp.text}")
    return resp


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.send_test_webhook <tenant_id> [decline_code]")
        sys.exit(1)
    tenant_id_arg = sys.argv[1]
    decline_code_arg = sys.argv[2] if len(sys.argv) > 2 else "insufficient_funds"
    send(tenant_id_arg, decline_code_arg)

"""
Stripe webhook signature verification (the Stripe-Signature header scheme:
t=<timestamp>,v1=<hmac_sha256_hex>). Same algorithm as the original architecture
spec's Module 3, pulled into its own module so it's independently testable and
reusable across gateways that use the same HMAC-over-timestamp+payload pattern
(Razorpay and Adyen both do something structurally similar).
"""
import hmac
import hashlib
import time


class SignatureVerificationError(Exception):
    pass


def verify_stripe_signature(
    payload: bytes,
    sig_header: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> None:
    """Raises SignatureVerificationError if the signature is invalid, expired, or
    malformed. Returns None (no exception) if valid."""
    if not sig_header:
        raise SignatureVerificationError("Missing Stripe-Signature header.")

    try:
        parts = dict(item.split("=", 1) for item in sig_header.split(","))
        timestamp = parts["t"]
        signature = parts["v1"]
    except (ValueError, KeyError):
        raise SignatureVerificationError("Malformed Stripe-Signature header.")

    if abs(int(time.time()) - int(timestamp)) > tolerance_seconds:
        raise SignatureVerificationError("Signature timestamp outside tolerance (possible replay).")

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected_sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        raise SignatureVerificationError("Signature mismatch.")


def sign_payload(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Builds a valid Stripe-Signature header value for a given payload. Used by
    the test-webhook script (and by tests) — this is the inverse of verification,
    not something the app itself calls in the request path."""
    timestamp = timestamp or int(time.time())
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"

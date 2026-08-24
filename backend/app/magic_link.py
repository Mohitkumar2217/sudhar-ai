"""
Signed, short-lived "update your payment method" links. A customer in dunning
gets one of these embedded in their email instead of being asked to log in —
the JWT itself is the authentication, scoped to exactly one invoice and expiring
in 15 minutes.
"""
import os
import time

import jwt

MAGIC_LINK_SECRET = os.getenv("MAGIC_LINK_SECRET", "local_dev_magic_link_secret")
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "http://localhost:3000/update")
TTL_SECONDS = 900  # 15 minutes


class MagicLinkError(Exception):
    """Raised for both expired and tampered/invalid tokens — the caller doesn't
    need to distinguish them, and not distinguishing them avoids leaking whether
    a token *would* have been valid had it not expired."""


def generate_magic_link(tenant_id: str, customer_id: str, invoice_id: str) -> str:
    payload = {
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "invoice_id": invoice_id,
        "exp": int(time.time()) + TTL_SECONDS,
    }
    token = jwt.encode(payload, MAGIC_LINK_SECRET, algorithm="HS256")
    return f"{PORTAL_BASE_URL}?token={token}"


def decode_magic_link(token: str) -> dict:
    try:
        return jwt.decode(token, MAGIC_LINK_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise MagicLinkError("This link has expired. Please request a new one.")
    except jwt.InvalidTokenError:
        raise MagicLinkError("This link is invalid.")

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime

from app.db import Base


class WebhookEvent(Base):
    """Tracks processed Stripe event IDs so a re-delivered webhook (Stripe retries
    on any non-2xx response) is a no-op instead of double-processing a charge."""
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True)  # the Stripe event id itself, e.g. evt_...
    tenant_id = Column(String, nullable=False)
    event_type = Column(String(100), nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)

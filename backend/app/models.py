import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, BigInteger, Numeric, DateTime, Boolean,
    ForeignKey, UniqueConstraint, CheckConstraint, Text
)
from sqlalchemy.orm import relationship

from app.db import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    customers = relationship("Customer", back_populates="tenant", cascade="all, delete-orphan")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("tenant_id", "external_customer_id", name="unique_tenant_customer"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    external_customer_id = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    mrr_cents = Column(BigInteger, nullable=False, default=0)
    health_score = Column(Numeric(3, 2), default=1.00)
    days_active_past_30d = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="customers")
    invoices = relationship("FailedInvoice", back_populates="customer", cascade="all, delete-orphan")


class FailedInvoice(Base):
    __tablename__ = "failed_invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_id", name="unique_tenant_invoice"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(String(255), nullable=False)
    amount_due_cents = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    raw_decline_code = Column(String(100), nullable=False)
    iso_8583_code = Column(String(10))
    failure_type = Column(String(30), nullable=False)  # HARD_DECLINE / SOFT_DECLINE / TECHNICAL_FAILURE / DISPUTED_CHURN
    status = Column(String(30), nullable=False, default="PENDING")
    attempt_count = Column(Integer, nullable=False, default=1)
    next_action_scheduled_at = Column(DateTime)
    recovered_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship("Customer", back_populates="invoices")
    actions = relationship("RecoveryAction", back_populates="invoice", cascade="all, delete-orphan")


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(String, primary_key=True, default=gen_uuid)
    invoice_id = Column(String, ForeignKey("failed_invoices.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(50), nullable=False)  # HEADLESS_RETRY / DUNNING_EMAIL / CARD_UPDATED
    channel = Column(String(50))
    message_subject = Column(Text)
    message_body = Column(Text)
    is_successful = Column(Boolean)

    # Snapshotted at the moment this action was taken — NOT joined live from
    # FailedInvoice, because attempt_count and decline context can change after
    # the fact. Training data extraction depends on these being the value AT
    # THE TIME of this specific attempt, not the invoice's current/final state.
    attempt_number = Column(Integer)
    decline_code_snapshot = Column(String(100))
    health_score_snapshot = Column(Numeric(3, 2))
    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("FailedInvoice", back_populates="actions")

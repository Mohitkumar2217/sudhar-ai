"""
Generates realistic fake data for PostgreSQL so the app is demoable without real Stripe webhooks.
Run with: python -m app.seed
"""
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from dotenv import load_dotenv

load_dotenv()

from app.db import Base, engine, SessionLocal
from app.models import Tenant, Customer, FailedInvoice, RecoveryAction

DECLINE_CODES_WEIGHTED = (
    ["insufficient_funds"] * 30
    + ["expired_card"] * 15
    + ["do_not_honor"] * 15
    + ["try_again_later"] * 12
    + ["processing_error"] * 10
    + ["card_velocity_exceeded"] * 8
    + ["lost_card"] * 4
    + ["stolen_card"] * 3
    + ["pickup_card"] * 3
)

FIRST_NAMES = ["Aarav", "Priya", "Jordan", "Maya", "Liam", "Sofia", "Kenji", "Zara", "Noah", "Elena"]
LAST_NAMES = ["Sharma", "Patel", "Kim", "Garcia", "Novak", "Chen", "Reyes", "Khan", "Müller", "Brown"]


def clean_database(db):
    """Truncates PostgreSQL tables cleanly with cascade, or recreates them for SQLite."""
    if engine.dialect.name == "postgresql":
        db.execute(text("TRUNCATE TABLE recovery_actions, failed_invoices, customers, tenants RESTART IDENTITY CASCADE;"))
        db.commit()
    else:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)


def run(num_customers: int = 60, num_invoices: int = 200) -> None:
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        clean_database(db)

        # 1. Create Tenant
        tenant = Tenant(name="Acme SaaS Inc")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        # 2. Create Customers
        customers = []
        for i in range(num_customers):
            name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            customer = Customer(
                tenant_id=tenant.id,
                external_customer_id=f"cus_{1000 + i}",
                email=f"{name.lower().replace(' ', '.')}{i}@example.com",
                name=name,
                mrr_cents=random.choice([1900, 4900, 9900, 19900, 49900, 99900]),
                health_score=round(random.uniform(0.05, 1.0), 2),
                days_active_past_30d=random.randint(0, 30),
            )
            db.add(customer)
            customers.append(customer)
        db.commit()

        # 3. Create Failed Invoices
        for i in range(num_invoices):
            customer = random.choice(customers)
            created = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 10))
            invoice = FailedInvoice(
                tenant_id=tenant.id,
                customer_id=customer.id,
                invoice_id=f"in_{2000 + i}",
                amount_due_cents=customer.mrr_cents,
                raw_decline_code=random.choice(DECLINE_CODES_WEIGHTED),
                failure_type="SOFT_DECLINE",
                status="PENDING",
                attempt_count=1,
                created_at=created,
                updated_at=created,
            )
            db.add(invoice)
        db.commit()
        print(f"Successfully seeded {len(customers)} customers and {num_invoices} invoices into PostgreSQL ({tenant.name}).")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run()
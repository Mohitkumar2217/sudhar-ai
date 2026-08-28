"""
Generates realistic fake data so the app is demoable without wiring real Stripe
webhooks. Run with: python -m app.seed
"""
import random
from datetime import datetime, timedelta

from app.db import Base, engine, SessionLocal
from app.models import Tenant, Customer, FailedInvoice

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


def run(num_customers: int = 60, num_invoices: int = 200) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        tenant = db.query(Tenant).filter(Tenant.name == "Acme SaaS Inc").first()
        if not tenant:
            tenant = Tenant(name="Acme SaaS Inc")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        customers = []
        for i in range(num_customers):
            name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            customer = Customer(
                tenant_id=tenant.id,
                external_customer_id=f"cus_{1000 + i}",
                email=f"{name.lower().replace(' ', '.')}@example.com",
                name=name,
                mrr_cents=random.choice([1900, 4900, 9900, 19900, 49900, 99900]),
                health_score=round(random.uniform(0.05, 1.0), 2),
                days_active_past_30d=random.randint(0, 30),
            )
            db.add(customer)
            customers.append(customer)
        db.commit()

        for i in range(num_invoices):
            customer = random.choice(customers)
            created = datetime.utcnow() - timedelta(days=random.randint(0, 10))
            invoice = FailedInvoice(
                tenant_id=tenant.id,
                customer_id=customer.id,
                invoice_id=f"in_{2000 + i}",
                amount_due_cents=customer.mrr_cents,
                raw_decline_code=random.choice(DECLINE_CODES_WEIGHTED),
                failure_type="SOFT_DECLINE",  # placeholder, set properly on first classification tick
                status="PENDING",
                attempt_count=1,
                created_at=created,
                updated_at=created,
            )
            db.add(invoice)
        db.commit()
        print(f"Seeded {len(customers)} customers and {num_invoices} failed invoices for tenant '{tenant.name}'.")
    finally:
        db.close()


if __name__ == "__main__":
    run()

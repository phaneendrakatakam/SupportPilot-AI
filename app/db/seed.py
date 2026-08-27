from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Base, Customer, Document, DocumentChunk, ServiceIncident, Subscription
from app.db.session import SessionLocal, engine


def dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


CUSTOMERS = [
    Customer(
        customer_id="CUS-1001",
        name="Arjun Rao",
        email="arjun.rao@example.test",
        account_status="ACTIVE",
        created_at=dt(2025, 1, 10),
    ),
    Customer(
        customer_id="CUS-1002",
        name="Priya Sharma",
        email="priya.sharma@example.test",
        account_status="ACTIVE",
        created_at=dt(2025, 2, 15),
    ),
    Customer(
        customer_id="CUS-1003",
        name="Rahul Verma",
        email="rahul.verma@example.test",
        account_status="SUSPENDED",
        created_at=dt(2025, 3, 20),
    ),
    Customer(
        customer_id="CUS-1007",
        name="Ananya Reddy",
        email="ananya.reddy@example.test",
        account_status="ACTIVE",
        created_at=dt(2025, 6, 7),
    ),
]

SUBSCRIPTIONS = [
    Subscription(
        subscription_id="SUB-1001",
        customer_id="CUS-1001",
        plan="BASIC",
        status="ACTIVE",
        requested_plan=None,
        start_date=dt(2025, 1, 10),
        last_sync_status="SUCCESS",
    ),
    Subscription(
        subscription_id="SUB-1002",
        customer_id="CUS-1002",
        plan="PRO",
        status="ACTIVE",
        requested_plan=None,
        start_date=dt(2025, 2, 15),
        last_sync_status="SUCCESS",
    ),
    Subscription(
        subscription_id="SUB-1003",
        customer_id="CUS-1003",
        plan="PRO",
        status="SUSPENDED",
        requested_plan=None,
        start_date=dt(2025, 3, 20),
        last_sync_status="SUCCESS",
    ),
    Subscription(
        subscription_id="SUB-1007",
        customer_id="CUS-1007",
        plan="BASIC",
        status="ACTIVE",
        requested_plan="PRO",
        start_date=dt(2025, 6, 7),
        last_sync_status="FAILED",
    ),
]

INCIDENTS = [
    ServiceIncident(
        incident_id="INC-2001",
        service="core",
        region="EU",
        status="ACTIVE",
        severity="SEV2",
        description="Elevated login errors for a subset of customers in the EU region.",
        started_at=dt(2026, 8, 25),
    ),
    ServiceIncident(
        incident_id="INC-1998",
        service="core",
        region="IN",
        status="RESOLVED",
        severity="SEV3",
        description="Intermittent dashboard latency in India; incident resolved.",
        started_at=dt(2026, 8, 20),
        resolved_at=dt(2026, 8, 20),
    ),
]

KNOWLEDGE = {
    "refund_policy.md": (
        "Refund Policy",
        "CloudDesk subscription charges are generally non-refundable after a billing cycle begins. "
        "A duplicate charge or a confirmed billing error may be reviewed by support. "
        "Customers should not be promised a refund unless the policy criteria are satisfied."
    ),
    "subscription_changes.md": (
        "Subscription Upgrade and Downgrade Policy",
        "Plan upgrades normally take effect after payment confirmation and a successful subscription sync. "
        "If payment succeeds but the requested plan is not applied, support should verify account and "
        "subscription state before escalation or approved remediation."
    ),
    "service_status.md": (
        "Service Availability Guidance",
        "When a customer reports that CloudDesk is unavailable, support should check the service status "
        "for the affected service and region before concluding that the issue is account-specific."
    ),
    "support_scope.md": (
        "Support Scope",
        "The support agent may answer documented product and policy questions and inspect authorized "
        "synthetic account data through approved tools. Unsupported actions and unrelated requests must "
        "not be presented as completed."
    ),
}


def seed() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for customer in CUSTOMERS:
            if db.get(Customer, customer.customer_id) is None:
                db.add(customer)

        for subscription in SUBSCRIPTIONS:
            if db.get(Subscription, subscription.subscription_id) is None:
                db.add(subscription)

        for incident in INCIDENTS:
            if db.get(ServiceIncident, incident.incident_id) is None:
                db.add(incident)

        db.flush()

        for source, (title, content) in KNOWLEDGE.items():
            existing = db.scalar(select(Document).where(Document.source == source))
            if existing is not None:
                continue
            document = Document(title=title, source=source)
            db.add(document)
            db.flush()
            db.add(DocumentChunk(document_id=document.document_id, chunk_index=0, content=content))

        db.commit()

    print("CloudDesk Day-1 seed completed.")


if __name__ == "__main__":
    seed()

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db.models import (
    Customer,
    Document,
    DocumentChunk,
    Payment,
    ServiceIncident,
    Subscription,
)
from app.db.schema import ensure_schema
from app.db.session import SessionLocal


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge_base"


def dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


CUSTOMERS = [
    ("CUS-1001", "Arjun Rao", "arjun.rao@example.test", "ACTIVE", dt(2025, 1, 10)),
    ("CUS-1002", "Priya Sharma", "priya.sharma@example.test", "ACTIVE", dt(2025, 2, 15)),
    ("CUS-1003", "Rahul Verma", "rahul.verma@example.test", "SUSPENDED", dt(2025, 3, 20)),
    ("CUS-1004", "Maya Singh", "maya.singh@example.test", "ACTIVE", dt(2025, 4, 12)),
    ("CUS-1005", "Aditya Nair", "aditya.nair@example.test", "ACTIVE", dt(2025, 5, 2)),
    ("CUS-1006", "Neha Iyer", "neha.iyer@example.test", "ACTIVE", dt(2025, 5, 20)),
    ("CUS-1007", "Ananya Reddy", "ananya.reddy@example.test", "ACTIVE", dt(2025, 6, 7)),
]

SUBSCRIPTIONS = [
    ("SUB-1001", "CUS-1001", "BASIC", "ACTIVE", None, "SUCCESS", dt(2025, 1, 10)),
    ("SUB-1002", "CUS-1002", "PRO", "ACTIVE", None, "SUCCESS", dt(2025, 2, 15)),
    ("SUB-1003", "CUS-1003", "PRO", "SUSPENDED", None, "SUCCESS", dt(2025, 3, 20)),
    ("SUB-1004", "CUS-1004", "BASIC", "ACTIVE", "PRO", "PENDING", dt(2025, 4, 12)),
    ("SUB-1005", "CUS-1005", "BASIC", "ACTIVE", "PRO", "FAILED", dt(2025, 5, 2)),
    ("SUB-1006", "CUS-1006", "PRO", "ACTIVE", "PRO", "SUCCESS", dt(2025, 5, 20)),
    ("SUB-1007", "CUS-1007", "BASIC", "ACTIVE", "PRO", "FAILED", dt(2025, 6, 7)),
]

PAYMENTS = [
    ("PAY-3001", "CUS-1001", "TXN-CD-3001", "PRO", Decimal("29.00"), "USD", "FAILED", dt(2026, 8, 20)),
    ("PAY-3002", "CUS-1002", "TXN-CD-3002", "PRO", Decimal("29.00"), "USD", "SUCCESS", dt(2026, 8, 22)),
    ("PAY-3004", "CUS-1004", "TXN-CD-3004", "PRO", Decimal("29.00"), "USD", "PENDING", dt(2026, 8, 26)),
    ("PAY-3006", "CUS-1006", "TXN-CD-3006", "PRO", Decimal("29.00"), "USD", "SUCCESS", dt(2026, 8, 27)),
    ("PAY-3007", "CUS-1007", "TXN-CD-3007", "PRO", Decimal("29.00"), "USD", "SUCCESS", dt(2026, 8, 27)),
]

INCIDENTS = [
    (
        "INC-2001", "core", "EU", "ACTIVE", "SEV2",
        "Elevated login errors for a subset of customers in the EU region.",
        dt(2026, 8, 25), None,
    ),
    (
        "INC-1998", "core", "IN", "RESOLVED", "SEV3",
        "Intermittent dashboard latency in India; incident resolved.",
        dt(2026, 8, 20), dt(2026, 8, 20),
    ),
]


def seed_data() -> None:
    ensure_schema()

    with SessionLocal() as db:
        for customer_id, name, email, status, created_at in CUSTOMERS:
            item = db.get(Customer, customer_id)
            if item is None:
                item = Customer(customer_id=customer_id)
                db.add(item)
            item.name = name
            item.email = email
            item.account_status = status
            item.created_at = created_at

        db.flush()

        for sub_id, customer_id, plan, status, requested, sync, start_date in SUBSCRIPTIONS:
            item = db.get(Subscription, sub_id)
            if item is None:
                item = Subscription(subscription_id=sub_id, customer_id=customer_id, plan=plan, status=status)
                db.add(item)
            item.customer_id = customer_id
            item.plan = plan
            item.status = status
            item.requested_plan = requested
            item.last_sync_status = sync
            item.start_date = start_date

        for pay_id, customer_id, ref, plan, amount, currency, status, payment_date in PAYMENTS:
            item = db.get(Payment, pay_id)
            if item is None:
                item = Payment(
                    payment_id=pay_id,
                    customer_id=customer_id,
                    transaction_reference=ref,
                    plan=plan,
                    amount=amount,
                    status=status,
                )
                db.add(item)
            item.customer_id = customer_id
            item.transaction_reference = ref
            item.plan = plan
            item.amount = amount
            item.currency = currency
            item.status = status
            item.payment_date = payment_date

        for inc_id, service, region, status, severity, description, started, resolved in INCIDENTS:
            item = db.get(ServiceIncident, inc_id)
            if item is None:
                item = ServiceIncident(
                    incident_id=inc_id,
                    service=service,
                    status=status,
                    severity=severity,
                    description=description,
                )
                db.add(item)
            item.service = service
            item.region = region
            item.status = status
            item.severity = severity
            item.description = description
            item.started_at = started
            item.resolved_at = resolved

        db.flush()

        for file_path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            source = file_path.name
            content = file_path.read_text(encoding="utf-8").strip()
            first = content.splitlines()[0] if content else source
            title = first.lstrip("#").strip() or source

            document = db.scalar(select(Document).where(Document.source == source))
            if document is None:
                document = Document(title=title, source=source)
                db.add(document)
                db.flush()
            else:
                document.title = title

            chunk = db.scalar(
                select(DocumentChunk).where(
                    DocumentChunk.document_id == document.document_id,
                    DocumentChunk.chunk_index == 0,
                )
            )
            if chunk is None:
                db.add(
                    DocumentChunk(
                        document_id=document.document_id,
                        chunk_index=0,
                        content=content,
                        embedding=None,
                    )
                )
            elif chunk.content != content:
                chunk.content = content
                chunk.embedding = None

        db.commit()

    print("CloudDesk V2 seed completed.")


if __name__ == "__main__":
    seed_data()

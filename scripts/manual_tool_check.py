import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.schemas import (
    CustomerLookupInput,
    PaymentLookupInput,
    ServiceStatusInput,
    SubscriptionLookupInput,
)
from app.db.seed import seed_data
from app.db.session import SessionLocal
from app.tools.customer import get_customer
from app.tools.payment import get_payment_status
from app.tools.service_status import get_service_status
from app.tools.subscription import get_subscription


def main() -> None:
    seed_data()
    with SessionLocal() as db:
        print(get_customer(db, CustomerLookupInput(customer_id="CUS-1007")).model_dump())
        print(get_subscription(db, SubscriptionLookupInput(customer_id="CUS-1007")).model_dump())
        print(get_payment_status(db, PaymentLookupInput(customer_id="CUS-1007")).model_dump())
        print(get_service_status(db, ServiceStatusInput(service="core", region="EU")).model_dump())


if __name__ == "__main__":
    main()

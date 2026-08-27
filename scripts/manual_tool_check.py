from app.agent.schemas import (
    CustomerLookupInput,
    KnowledgeSearchInput,
    ServiceStatusInput,
    SubscriptionLookupInput,
)
from app.db.session import SessionLocal
from app.tools.customer import get_customer
from app.tools.knowledge import search_knowledge_base
from app.tools.service_status import get_service_status
from app.tools.subscription import get_subscription


def main() -> None:
    with SessionLocal() as db:
        print(get_customer(db, CustomerLookupInput(customer_id="CUS-1001")).model_dump())
        print(get_subscription(db, SubscriptionLookupInput(customer_id="CUS-1007")).model_dump())
        print(get_service_status(db, ServiceStatusInput(service="core", region="IN")).model_dump())
        print(search_knowledge_base(db, KnowledgeSearchInput(query="refund policy")).model_dump())


if __name__ == "__main__":
    main()

from sqlalchemy.orm import Session

from app.agent.schemas import CustomerLookupInput, CustomerResult
from app.db.models import Customer


def get_customer(db: Session, payload: CustomerLookupInput) -> CustomerResult:
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        return CustomerResult(status="NOT_FOUND", error="Customer was not found.")

    return CustomerResult(
        status="SUCCESS",
        customer_id=customer.customer_id,
        name=customer.name,
        email=customer.email,
        account_status=customer.account_status,
    )

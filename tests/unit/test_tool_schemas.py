import pytest
from pydantic import ValidationError

from app.agent.schemas import (
    CustomerLookupInput,
    KnowledgeSearchInput,
    ServiceStatusInput,
    SubscriptionLookupInput,
)


def test_customer_lookup_accepts_valid_customer_id() -> None:
    payload = CustomerLookupInput(customer_id="CUS-1001")
    assert payload.customer_id == "CUS-1001"


def test_subscription_lookup_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SubscriptionLookupInput(customer_id="CUS-1001", plan="PRO")


def test_service_status_has_safe_default_service() -> None:
    payload = ServiceStatusInput()
    assert payload.service == "core"


def test_knowledge_top_k_is_bounded() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSearchInput(query="refund policy", top_k=50)

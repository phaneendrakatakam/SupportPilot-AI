import pytest
from pydantic import ValidationError

from app.agent.schemas import (
    CustomerLookupInput,
    KnowledgeSearchInput,
    PaymentLookupInput,
    PaymentResult,
    ResolutionDecision,
    ServiceStatusInput,
    SubscriptionLookupInput,
)


def test_customer_lookup_accepts_valid_id() -> None:
    value = CustomerLookupInput(customer_id="CUS-1001")
    assert value.customer_id == "CUS-1001"


def test_customer_lookup_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CustomerLookupInput(customer_id="CUS-1001", email="x@example.test")


def test_subscription_lookup_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SubscriptionLookupInput(customer_id="CUS-1001", plan="PRO")


def test_payment_lookup_accepts_optional_payment_id() -> None:
    value = PaymentLookupInput(customer_id="CUS-1007", payment_id="PAY-3007")
    assert value.payment_id == "PAY-3007"


def test_payment_lookup_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PaymentLookupInput(customer_id="CUS-1007", amount="29")


def test_service_status_defaults_to_core() -> None:
    assert ServiceStatusInput().service == "core"


def test_knowledge_top_k_is_bounded() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSearchInput(query="refund policy", top_k=50)


def test_knowledge_query_has_minimum_length() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSearchInput(query="x")


def test_resolution_status_is_validated() -> None:
    with pytest.raises(ValidationError):
        ResolutionDecision(
            resolution_status="MAYBE",
            issue_type="test_issue",
            summary="Not valid.",
            evidence=[],
        )


def test_payment_business_status_is_validated() -> None:
    with pytest.raises(ValidationError):
        PaymentResult(
            status="SUCCESS",
            customer_id="CUS-1007",
            payment_status="UNKNOWN",
        )

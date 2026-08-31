from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ToolStatus = Literal["SUCCESS", "NOT_FOUND", "ERROR", "NOT_READY"]
PaymentStatus = Literal["SUCCESS", "FAILED", "PENDING", "REFUNDED"]
ResolutionStatus = Literal[
    "RESOLVED",
    "NEEDS_INFORMATION",
    "UNRESOLVED",
    "ESCALATION_REQUIRED",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerLookupInput(StrictModel):
    customer_id: str = Field(min_length=3, max_length=32)


class CustomerResult(StrictModel):
    status: ToolStatus
    customer_id: str | None = None
    name: str | None = None
    email: str | None = None
    account_status: str | None = None
    error: str | None = None


class SubscriptionLookupInput(StrictModel):
    customer_id: str = Field(min_length=3, max_length=32)


class SubscriptionResult(StrictModel):
    status: ToolStatus
    subscription_id: str | None = None
    customer_id: str | None = None
    plan: str | None = None
    subscription_status: str | None = None
    requested_plan: str | None = None
    last_sync_status: str | None = None
    error: str | None = None


class PaymentLookupInput(StrictModel):
    customer_id: str = Field(min_length=3, max_length=32)
    payment_id: str | None = Field(default=None, min_length=3, max_length=32)


class PaymentResult(StrictModel):
    status: ToolStatus
    payment_id: str | None = None
    customer_id: str | None = None
    transaction_reference: str | None = None
    plan: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    payment_status: PaymentStatus | None = None
    payment_date: str | None = None
    error: str | None = None


class ServiceStatusInput(StrictModel):
    service: str = Field(default="core", min_length=2, max_length=80)
    region: str | None = Field(default=None, max_length=32)


class ServiceIncidentResult(StrictModel):
    incident_id: str
    service: str
    region: str | None
    status: str
    severity: str
    description: str


class ServiceStatusResult(StrictModel):
    status: ToolStatus
    active_incidents: list[ServiceIncidentResult] = Field(default_factory=list)
    error: str | None = None


class KnowledgeSearchInput(StrictModel):
    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


class KnowledgePassage(StrictModel):
    content: str
    source: str
    score: float = Field(ge=0.0, le=1.0)


class KnowledgeSearchResult(StrictModel):
    status: ToolStatus
    results: list[KnowledgePassage] = Field(default_factory=list)
    retrieval_mode: str = "semantic-pgvector-gemini"
    error: str | None = None


class ResolutionDecision(StrictModel):
    resolution_status: ResolutionStatus
    issue_type: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=2, max_length=2000)
    evidence: list[str] = Field(default_factory=list)

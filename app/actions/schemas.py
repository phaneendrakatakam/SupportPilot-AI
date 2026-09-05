from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ActionName = Literal[
    "retry_subscription_sync",
    "create_support_ticket",
    "request_refund_review",
]

ApprovalStatus = Literal[
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
]

ExecutionStatus = Literal[
    "NOT_STARTED",
    "EXECUTING",
    "SUCCEEDED",
    "FAILED",
    "SKIPPED",
]

VerificationStatus = Literal[
    "NOT_REQUIRED",
    "PENDING",
    "VERIFIED",
    "FAILED",
]

TicketPriority = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
    "URGENT",
]


class StrictActionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RetrySubscriptionSyncInput(StrictActionModel):
    customer_id: str = Field(min_length=3, max_length=32)
    requested_plan: str = Field(min_length=2, max_length=32)


class CreateSupportTicketInput(StrictActionModel):
    customer_id: str = Field(min_length=3, max_length=32)
    issue_type: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=2, max_length=2000)
    priority: TicketPriority = "HIGH"
    evidence: list[str] = Field(min_length=1, max_length=20)


class RequestRefundReviewInput(StrictActionModel):
    customer_id: str = Field(min_length=3, max_length=32)
    payment_id: str = Field(min_length=3, max_length=32)
    reason: str = Field(min_length=2, max_length=2000)


class ActionRecommendation(StrictActionModel):
    action_name: ActionName
    arguments: dict[str, Any]
    reason: str = Field(min_length=2, max_length=2000)
    issue_type: str = Field(min_length=2, max_length=120)
    approval_required: Literal[True] = True


class ApprovalDecisionInput(StrictActionModel):
    decided_by: str = Field(min_length=2, max_length=120)
    reason: str | None = Field(
        default=None,
        min_length=2,
        max_length=1000,
    )


class ActionLifecycleState(StrictActionModel):
    approval_status: ApprovalStatus = "PENDING_APPROVAL"
    execution_status: ExecutionStatus = "NOT_STARTED"
    verification_status: VerificationStatus = "PENDING"
    error: str | None = None


class ControlledActionResult(StrictActionModel):
    execution_status: ExecutionStatus
    verification_status: VerificationStatus
    before_state: dict[str, Any] | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    error: str | None = None


class AgentActionProposalResponse(StrictActionModel):
    """
    Compact action proposal returned from the chat/orchestrator flow.
    """

    proposal_id: str
    action_name: ActionName
    arguments: dict[str, Any]
    reason: str
    issue_type: str
    approval_required: bool
    approval_status: ApprovalStatus
    proposed_at: datetime | None = None


class ActionProposalResponse(StrictActionModel):
    proposal_id: str
    conversation_id: str
    run_id: str
    customer_id: str
    action_name: ActionName
    arguments: dict[str, Any]
    reason: str
    issue_type: str
    approval_required: bool
    approval_status: ApprovalStatus
    proposed_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None


class ActionExecutionResponse(StrictActionModel):
    execution_id: str
    proposal_id: str
    execution_status: ExecutionStatus
    verification_status: VerificationStatus
    before_state: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    verified_at: datetime | None = None
    created_at: datetime


class ActionDetailResponse(StrictActionModel):
    proposal: ActionProposalResponse
    execution: ActionExecutionResponse | None = None

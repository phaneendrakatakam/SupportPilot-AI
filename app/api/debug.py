import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.db.models import (
    ActionExecution,
    ActionProposal,
    AgentRun,
    Conversation,
    RefundReview,
    SupportTicket,
    ToolExecution,
)
from app.db.schema import ensure_schema
from app.db.session import SessionLocal


router = APIRouter(
    prefix="/api/v1/debug",
    tags=["debug"],
)


SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "card_number",
    "email",
    "password",
    "secret",
    "token",
}


class ToolExecutionInspectorResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    execution_id: str
    tool_name: str
    arguments: dict[str, Any]
    result_status: str
    result: dict[str, Any] | list[Any] | str | None
    latency_ms: float | None = None
    error: str | None = None
    created_at: datetime


class ActionExecutionInspectorResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    execution_id: str
    execution_status: str
    verification_status: str
    before_state: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    verified_at: datetime | None = None


class ActionProposalInspectorResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    proposal_id: str
    action_name: str
    arguments: dict[str, Any]
    reason: str
    issue_type: str
    approval_required: bool
    approval_status: str
    proposed_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None
    execution: ActionExecutionInspectorResponse | None = None
    business_object: dict[str, Any] | None = None


class AgentRunInspectorResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    run_id: str
    conversation_id: str | None = None
    customer_id: str | None = None
    prompt_version: str
    intent: str | None = None
    resolution_status: str | None = None
    issue_type: str | None = None
    resolution_summary: str | None = None
    request_message: str | None = None
    final_response: str | None = None
    latency_ms: float | None = None
    error: str | None = None
    created_at: datetime
    trace: list[dict[str, Any]]
    tool_executions: list[
        ToolExecutionInspectorResponse
    ]
    action_proposals: list[
        ActionProposalInspectorResponse
    ]


class AgentRunSummaryResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    run_id: str
    prompt_version: str
    intent: str | None = None
    resolution_status: str | None = None
    latency_ms: float | None = None
    error: str | None = None
    created_at: datetime


class ConversationRunsResponse(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid"
    )

    conversation_id: str
    customer_id: str | None = None
    runs: list[
        AgentRunSummaryResponse
    ]


def _safe_json_load(
    value: str | None,
    fallback: Any,
) -> Any:
    if not value:
        return fallback

    try:
        return json.loads(
            value
        )

    except (
        TypeError,
        json.JSONDecodeError,
    ):
        return fallback


def _mask_debug_payload(
    value: Any,
) -> Any:
    """
    Recursively mask fields that should not be displayed in an inspector.

    SupportPilot currently uses synthetic data, but keeping this boundary in
    place makes the debug surface safer if tool contracts grow later.
    """

    if isinstance(
        value,
        dict,
    ):
        masked: dict[
            str,
            Any,
        ] = {}

        for key, item in value.items():
            normalized_key = (
                str(key)
                .strip()
                .lower()
            )

            if normalized_key in SENSITIVE_KEYS:
                masked[
                    str(key)
                ] = "[MASKED]"
            else:
                masked[
                    str(key)
                ] = (
                    _mask_debug_payload(
                        item
                    )
                )

        return masked

    if isinstance(
        value,
        list,
    ):
        return [
            _mask_debug_payload(
                item
            )
            for item in value
        ]

    return value


def _tool_response(
    execution: ToolExecution,
) -> ToolExecutionInspectorResponse:
    arguments = _safe_json_load(
        execution.arguments_json,
        {},
    )

    result = _safe_json_load(
        execution.result_json,
        None,
    )

    return ToolExecutionInspectorResponse(
        execution_id=(
            execution.execution_id
        ),
        tool_name=(
            execution.tool_name
        ),
        arguments=(
            _mask_debug_payload(
                arguments
            )
        ),
        result_status=(
            execution.result_status
        ),
        result=(
            _mask_debug_payload(
                result
            )
        ),
        latency_ms=(
            execution.latency_ms
        ),
        error=execution.error,
        created_at=(
            execution.created_at
        ),
    )


def _action_execution_response(
    execution: ActionExecution,
) -> ActionExecutionInspectorResponse:
    return ActionExecutionInspectorResponse(
        execution_id=execution.execution_id,
        execution_status=execution.execution_status,
        verification_status=execution.verification_status,
        before_state=_mask_debug_payload(
            _safe_json_load(
                execution.before_state_json,
                None,
            )
        ),
        result=_mask_debug_payload(
            _safe_json_load(
                execution.result_json,
                None,
            )
        ),
        after_state=_mask_debug_payload(
            _safe_json_load(
                execution.after_state_json,
                None,
            )
        ),
        verification_result=_mask_debug_payload(
            _safe_json_load(
                execution.verification_result_json,
                None,
            )
        ),
        error=execution.error,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        verified_at=execution.verified_at,
    )


def _business_object(
    db,
    proposal: ActionProposal,
) -> dict[str, Any] | None:
    ticket = db.scalar(
        select(SupportTicket).where(
            SupportTicket.proposal_id
            == proposal.proposal_id
        )
    )

    if ticket is not None:
        return {
            "type": "support_ticket",
            "ticket_number": ticket.ticket_number,
            "priority": ticket.priority,
            "status": ticket.status,
            "issue_type": ticket.issue_type,
            "summary": ticket.summary,
            "evidence": _safe_json_load(
                ticket.evidence_json,
                [],
            ),
            "created_at": ticket.created_at.isoformat(),
        }

    review = db.scalar(
        select(RefundReview).where(
            RefundReview.proposal_id
            == proposal.proposal_id
        )
    )

    if review is not None:
        return {
            "type": "refund_review",
            "review_number": review.review_number,
            "payment_id": review.payment_id,
            "status": review.status,
            "reason": review.reason,
            "created_at": review.created_at.isoformat(),
        }

    return None


def _action_proposal_response(
    db,
    proposal: ActionProposal,
) -> ActionProposalInspectorResponse:
    execution = db.scalar(
        select(ActionExecution).where(
            ActionExecution.proposal_id
            == proposal.proposal_id
        )
    )

    return ActionProposalInspectorResponse(
        proposal_id=proposal.proposal_id,
        action_name=proposal.action_name,
        arguments=_mask_debug_payload(
            _safe_json_load(
                proposal.arguments_json,
                {},
            )
        ),
        reason=proposal.reason,
        issue_type=proposal.issue_type,
        approval_required=proposal.approval_required,
        approval_status=proposal.approval_status,
        proposed_at=proposal.proposed_at,
        decided_at=proposal.decided_at,
        decided_by=proposal.decided_by,
        execution=(
            _action_execution_response(
                execution
            )
            if execution is not None
            else None
        ),
        business_object=_mask_debug_payload(
            _business_object(
                db,
                proposal,
            )
        ),
    )


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunInspectorResponse,
)
def get_agent_run(
    run_id: str,
) -> AgentRunInspectorResponse:
    ensure_schema()

    """
    Return persisted structured run information for the internal inspector.

    This endpoint exposes tool calls, application decisions and persisted
    traces. It never exposes private model chain-of-thought.
    """

    with SessionLocal() as db:
        agent_run = db.get(
            AgentRun,
            run_id,
        )

        if agent_run is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Agent run not found: "
                    f"{run_id}"
                ),
            )

        conversation = None

        if agent_run.conversation_id:
            conversation = db.get(
                Conversation,
                agent_run.conversation_id,
            )

        executions = list(
            db.scalars(
                select(
                    ToolExecution
                )
                .where(
                    ToolExecution.run_id
                    == run_id
                )
                .order_by(
                    ToolExecution.created_at,
                    ToolExecution.execution_id,
                )
            ).all()
        )

        action_proposals = list(
            db.scalars(
                select(
                    ActionProposal
                )
                .where(
                    ActionProposal.run_id
                    == run_id
                )
                .order_by(
                    ActionProposal.proposed_at,
                    ActionProposal.proposal_id,
                )
            ).all()
        )

        trace = _safe_json_load(
            agent_run.trace_json,
            [],
        )

        if not isinstance(
            trace,
            list,
        ):
            trace = []

        return AgentRunInspectorResponse(
            run_id=agent_run.run_id,
            conversation_id=(
                agent_run.conversation_id
            ),
            customer_id=(
                conversation.customer_id
                if conversation
                else None
            ),
            prompt_version=(
                agent_run.prompt_version
            ),
            intent=agent_run.intent,
            resolution_status=(
                agent_run.resolution_status
            ),
            issue_type=(
                agent_run.issue_type
            ),
            resolution_summary=(
                agent_run.resolution_summary
            ),
            request_message=(
                agent_run.request_message
            ),
            final_response=(
                agent_run.final_response
            ),
            latency_ms=(
                agent_run.latency_ms
            ),
            error=agent_run.error,
            created_at=(
                agent_run.created_at
            ),
            trace=(
                _mask_debug_payload(
                    trace
                )
            ),
            tool_executions=[
                _tool_response(
                    execution
                )
                for execution in executions
            ],
            action_proposals=[
                _action_proposal_response(
                    db,
                    proposal,
                )
                for proposal in action_proposals
            ],
        )


@router.get(
    "/conversations/{conversation_id}/runs",
    response_model=ConversationRunsResponse,
)
def get_conversation_runs(
    conversation_id: str,
) -> ConversationRunsResponse:
    ensure_schema()

    with SessionLocal() as db:
        conversation = db.get(
            Conversation,
            conversation_id,
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Conversation not found: "
                    f"{conversation_id}"
                ),
            )

        runs = list(
            db.scalars(
                select(
                    AgentRun
                )
                .where(
                    AgentRun.conversation_id
                    == conversation_id
                )
                .order_by(
                    AgentRun.created_at.desc(),
                    AgentRun.run_id.desc(),
                )
            ).all()
        )

        return ConversationRunsResponse(
            conversation_id=(
                conversation.conversation_id
            ),
            customer_id=(
                conversation.customer_id
            ),
            runs=[
                AgentRunSummaryResponse(
                    run_id=run.run_id,
                    prompt_version=(
                        run.prompt_version
                    ),
                    intent=run.intent,
                    resolution_status=(
                        run.resolution_status
                    ),
                    latency_ms=(
                        run.latency_ms
                    ),
                    error=run.error,
                    created_at=(
                        run.created_at
                    ),
                )
                for run in runs
            ],
        )

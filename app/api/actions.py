import json
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.actions.schemas import (
    ActionDetailResponse,
    ApprovalStatus,
    ActionExecutionResponse,
    ActionProposalResponse,
    ApprovalDecisionInput,
)
from app.actions.service import (
    approve_action,
    execute_approved_action,
    proposal_equivalence_key,
    reject_action,
)
from app.db.models import (
    ActionExecution,
    ActionProposal,
)
from app.db.schema import ensure_schema
from app.db.session import SessionLocal
from app.services.customer_case import (
    persist_verified_customer_outcome,
)


router = APIRouter(
    prefix="/api/v1/actions",
    tags=["actions"],
)


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


def _proposal_response(
    proposal: ActionProposal,
) -> ActionProposalResponse:
    return ActionProposalResponse(
        proposal_id=proposal.proposal_id,
        conversation_id=proposal.conversation_id,
        run_id=proposal.run_id,
        customer_id=proposal.customer_id,
        action_name=proposal.action_name,
        arguments=_safe_json_load(
            proposal.arguments_json,
            {},
        ),
        reason=proposal.reason,
        issue_type=proposal.issue_type,
        approval_required=proposal.approval_required,
        approval_status=proposal.approval_status,
        proposed_at=proposal.proposed_at,
        decided_at=proposal.decided_at,
        decided_by=proposal.decided_by,
    )


def _execution_response(
    execution: ActionExecution,
) -> ActionExecutionResponse:
    return ActionExecutionResponse(
        execution_id=execution.execution_id,
        proposal_id=execution.proposal_id,
        execution_status=execution.execution_status,
        verification_status=execution.verification_status,
        before_state=_safe_json_load(
            execution.before_state_json,
            None,
        ),
        result=_safe_json_load(
            execution.result_json,
            None,
        ),
        after_state=_safe_json_load(
            execution.after_state_json,
            None,
        ),
        verification_result=_safe_json_load(
            execution.verification_result_json,
            None,
        ),
        error=execution.error,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        verified_at=execution.verified_at,
        created_at=execution.created_at,
    )


def _lifecycle_rank(
    proposal: ActionProposal,
    execution: ActionExecution | None,
) -> int:
    """
    Prefer the most-progressed proposal when old duplicate test records exist.
    """

    if (
        execution is not None
        and execution.verification_status
        == "VERIFIED"
    ):
        return 60

    if (
        execution is not None
        and execution.verification_status
        == "FAILED"
    ):
        return 55

    if (
        execution is not None
        and execution.execution_status
        == "SUCCEEDED"
    ):
        return 50

    if (
        execution is not None
        and execution.execution_status
        == "FAILED"
    ):
        return 45

    if proposal.approval_status == "APPROVED":
        return 40

    if proposal.approval_status == "PENDING_APPROVAL":
        return 30

    return 10


def _collapse_logical_duplicates(
    proposals: list[ActionProposal],
    executions_by_proposal: dict[str, ActionExecution],
) -> list[ActionProposal]:
    """
    Present one operator work item per logical action.

    REJECTED proposals remain independent historical decisions. Pending and
    approved duplicates are collapsed so old follow-up-generated proposals do
    not appear as separate actionable reviews.
    """

    chosen: dict[str, ActionProposal] = {}
    rejected: list[ActionProposal] = []

    for proposal in proposals:
        if proposal.approval_status == "REJECTED":
            rejected.append(
                proposal
            )
            continue

        key = proposal_equivalence_key(
            proposal
        )

        current = chosen.get(
            key
        )

        if current is None:
            chosen[key] = proposal
            continue

        current_execution = (
            executions_by_proposal.get(
                current.proposal_id
            )
        )
        proposal_execution = (
            executions_by_proposal.get(
                proposal.proposal_id
            )
        )

        current_rank = _lifecycle_rank(
            current,
            current_execution,
        )
        proposal_rank = _lifecycle_rank(
            proposal,
            proposal_execution,
        )

        if proposal_rank > current_rank:
            chosen[key] = proposal

        elif (
            proposal_rank == current_rank
            and proposal.proposed_at
            < current.proposed_at
        ):
            chosen[key] = proposal

    result = (
        list(chosen.values())
        + rejected
    )

    return sorted(
        result,
        key=lambda item: (
            item.proposed_at,
            item.proposal_id,
        ),
        reverse=True,
    )


def _not_found_or_conflict(
    exc: ValueError,
) -> HTTPException:
    detail = str(exc)

    if "not found" in detail.lower():
        return HTTPException(
            status_code=404,
            detail=detail,
        )

    return HTTPException(
        status_code=409,
        detail=detail,
    )


@router.get(
    "",
    response_model=list[ActionDetailResponse],
)
def list_actions(
    approval_status: ApprovalStatus | None = None,
    limit: int = 100,
) -> list[ActionDetailResponse]:
    """
    Return action proposals for the human-review queue.

    The endpoint is intentionally separate from the Gemini tool loop. It is
    an application/operator surface for already-persisted proposals only.
    """
    ensure_schema()

    safe_limit = max(
        1,
        min(
            limit,
            200,
        ),
    )

    with SessionLocal() as db:
        fetch_limit = min(
            max(
                safe_limit * 4,
                safe_limit,
            ),
            200,
        )

        proposals = list(
            db.scalars(
                select(ActionProposal)
                .order_by(
                    ActionProposal.proposed_at.desc(),
                    ActionProposal.proposal_id.desc(),
                )
                .limit(fetch_limit)
            ).all()
        )

        if not proposals:
            return []

        proposal_ids = [
            proposal.proposal_id
            for proposal in proposals
        ]

        executions = list(
            db.scalars(
                select(ActionExecution).where(
                    ActionExecution.proposal_id.in_(
                        proposal_ids
                    )
                )
            ).all()
        )

        executions_by_proposal = {
            execution.proposal_id: execution
            for execution in executions
        }

        proposals = (
            _collapse_logical_duplicates(
                proposals,
                executions_by_proposal,
            )
        )

        if approval_status is not None:
            proposals = [
                proposal
                for proposal in proposals
                if (
                    proposal.approval_status
                    == approval_status
                )
            ]

        proposals = proposals[
            :safe_limit
        ]

        return [
            ActionDetailResponse(
                proposal=_proposal_response(
                    proposal
                ),
                execution=(
                    _execution_response(
                        executions_by_proposal[
                            proposal.proposal_id
                        ]
                    )
                    if proposal.proposal_id
                    in executions_by_proposal
                    else None
                ),
            )
            for proposal in proposals
        ]


@router.get(
    "/{proposal_id}",
    response_model=ActionDetailResponse,
)
def get_action(
    proposal_id: str,
) -> ActionDetailResponse:
    ensure_schema()

    with SessionLocal() as db:
        proposal = db.get(
            ActionProposal,
            proposal_id,
        )

        if proposal is None:
            raise HTTPException(
                status_code=404,
                detail="Action proposal not found.",
            )

        execution = db.scalar(
            select(ActionExecution).where(
                ActionExecution.proposal_id
                == proposal_id
            )
        )

        return ActionDetailResponse(
            proposal=_proposal_response(
                proposal
            ),
            execution=(
                _execution_response(
                    execution
                )
                if execution is not None
                else None
            ),
        )


@router.post(
    "/{proposal_id}/approve",
    response_model=ActionProposalResponse,
)
def approve_action_proposal(
    proposal_id: str,
    payload: ApprovalDecisionInput,
) -> ActionProposalResponse:
    ensure_schema()

    with SessionLocal() as db:
        try:
            proposal = approve_action(
                db,
                proposal_id,
                payload,
            )
            db.commit()
            db.refresh(
                proposal
            )
        except ValueError as exc:
            db.rollback()
            raise _not_found_or_conflict(
                exc
            ) from exc

        return _proposal_response(
            proposal
        )


@router.post(
    "/{proposal_id}/reject",
    response_model=ActionProposalResponse,
)
def reject_action_proposal(
    proposal_id: str,
    payload: ApprovalDecisionInput,
) -> ActionProposalResponse:
    ensure_schema()

    with SessionLocal() as db:
        try:
            proposal = reject_action(
                db,
                proposal_id,
                payload,
            )
            db.commit()
            db.refresh(
                proposal
            )
        except ValueError as exc:
            db.rollback()
            raise _not_found_or_conflict(
                exc
            ) from exc

        return _proposal_response(
            proposal
        )


@router.post(
    "/{proposal_id}/execute",
    response_model=ActionExecutionResponse,
)
def execute_action_proposal(
    proposal_id: str,
) -> ActionExecutionResponse:
    ensure_schema()

    with SessionLocal() as db:
        try:
            proposal = db.get(
                ActionProposal,
                proposal_id,
            )

            execution = execute_approved_action(
                db,
                proposal_id,
            )

            if (
                proposal is not None
                and execution.verification_status
                == "VERIFIED"
            ):
                persist_verified_customer_outcome(
                    db,
                    proposal,
                    execution,
                )

            db.commit()
            db.refresh(
                execution
            )
        except PermissionError as exc:
            db.rollback()
            raise HTTPException(
                status_code=403,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            db.rollback()
            raise _not_found_or_conflict(
                exc
            ) from exc

        return _execution_response(
            execution
        )

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from google.genai import types
from sqlalchemy import delete, select

import app.agent.orchestrator as orchestrator

from app.agent.schemas import (
    PaymentResult,
    SubscriptionResult,
)
from app.db.models import (
    ActionExecution,
    ActionProposal,
    AgentRun,
    Conversation,
    Message,
    RefundReview,
    SupportTicket,
    ToolExecution,
)
from app.db.session import SessionLocal


class FakeModels:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = iter(responses)

    def generate_content(self, **_kwargs: Any) -> Any:
        return next(self._responses)


class FakeGeminiClient:
    def __init__(self, responses: list[Any]) -> None:
        self.models = FakeModels(responses)


def make_tool_call_response(
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    function_call = SimpleNamespace(
        name=tool_name,
        args=arguments,
    )

    model_content = types.Content(
        role="model",
        parts=[
            types.Part.from_text(
                text=f"Calling {tool_name}"
            )
        ],
    )

    return SimpleNamespace(
        function_calls=[function_call],
        candidates=[
            SimpleNamespace(
                content=model_content
            )
        ],
        text=None,
    )


def make_final_response(text: str) -> Any:
    return SimpleNamespace(
        function_calls=[],
        candidates=[],
        text=text,
    )


def install_fake_client(
    monkeypatch,
    responses: list[Any],
) -> None:
    fake_client = FakeGeminiClient(responses)

    monkeypatch.setattr(
        orchestrator.settings,
        "gemini_api_key",
        "test-api-key",
    )

    monkeypatch.setattr(
        orchestrator.genai,
        "Client",
        lambda **_kwargs: fake_client,
    )


def cleanup_conversation(
    conversation_id: str,
) -> None:
    with SessionLocal() as db:
        run_ids = list(
            db.scalars(
                select(
                    AgentRun.run_id
                ).where(
                    AgentRun.conversation_id
                    == conversation_id
                )
            ).all()
        )

        if run_ids:
            proposal_ids = list(
                db.scalars(
                    select(
                        ActionProposal.proposal_id
                    ).where(
                        ActionProposal.run_id.in_(
                            run_ids
                        )
                    )
                ).all()
            )

            if proposal_ids:
                db.execute(
                    delete(
                        ActionExecution
                    ).where(
                        ActionExecution.proposal_id.in_(
                            proposal_ids
                        )
                    )
                )
                db.execute(
                    delete(
                        SupportTicket
                    ).where(
                        SupportTicket.proposal_id.in_(
                            proposal_ids
                        )
                    )
                )
                db.execute(
                    delete(
                        RefundReview
                    ).where(
                        RefundReview.proposal_id.in_(
                            proposal_ids
                        )
                    )
                )
                db.execute(
                    delete(
                        ActionProposal
                    ).where(
                        ActionProposal.proposal_id.in_(
                            proposal_ids
                        )
                    )
                )

            db.execute(
                delete(
                    ToolExecution
                ).where(
                    ToolExecution.run_id.in_(
                        run_ids
                    )
                )
            )

        db.execute(
            delete(
                Message
            ).where(
                Message.conversation_id
                == conversation_id
            )
        )
        db.execute(
            delete(
                AgentRun
            ).where(
                AgentRun.conversation_id
                == conversation_id
            )
        )
        db.execute(
            delete(
                Conversation
            ).where(
                Conversation.conversation_id
                == conversation_id
            )
        )

        db.commit()


def test_run_agent_persists_retry_proposal_without_executing(
    monkeypatch,
) -> None:
    install_fake_client(
        monkeypatch,
        [
            make_tool_call_response(
                "get_subscription",
                {"customer_id": "CUS-1007"},
            ),
            make_tool_call_response(
                "get_payment_status",
                {"customer_id": "CUS-1007"},
            ),
            make_final_response(
                "The paid Pro upgrade has not been applied."
            ),
        ],
    )

    monkeypatch.setattr(
        orchestrator,
        "get_subscription",
        lambda _db, _payload: SubscriptionResult(
            status="SUCCESS",
            subscription_id="SUB-1007",
            customer_id="CUS-1007",
            plan="BASIC",
            subscription_status="ACTIVE",
            requested_plan="PRO",
            last_sync_status="FAILED",
        ),
    )

    monkeypatch.setattr(
        orchestrator,
        "get_payment_status",
        lambda _db, _payload: PaymentResult(
            status="SUCCESS",
            payment_id="PAY-3007",
            customer_id="CUS-1007",
            transaction_reference="TXN-CD-3007",
            plan="PRO",
            amount=Decimal("29.00"),
            currency="USD",
            payment_status="SUCCESS",
            payment_date=datetime(
                2026, 8, 27, tzinfo=timezone.utc
            ).isoformat(),
        ),
    )

    result = orchestrator.run_agent(
        message=(
            "I paid for Pro, but my account still shows Basic."
        ),
        customer_id="CUS-1007",
    )

    conversation_id = result["conversation_id"]

    try:
        proposal = result["action_proposal"]

        assert proposal is not None
        assert proposal["action_name"] == "retry_subscription_sync"
        assert proposal["approval_status"] == "PENDING_APPROVAL"

        action_events = [
            event
            for event in result["trace"]
            if event["type"] == "action_proposal"
        ]
        assert len(action_events) == 1

        with SessionLocal() as db:
            persisted = db.get(
                ActionProposal,
                proposal["proposal_id"],
            )

            assert persisted is not None
            assert persisted.run_id == result["run_id"]
            assert persisted.customer_id == "CUS-1007"

            execution = db.scalar(
                select(
                    ActionExecution
                ).where(
                    ActionExecution.proposal_id
                    == persisted.proposal_id
                )
            )

            assert execution is None

    finally:
        cleanup_conversation(
            conversation_id
        )


def test_run_agent_persists_refund_review_proposal(
    monkeypatch,
) -> None:
    install_fake_client(
        monkeypatch,
        [
            make_tool_call_response(
                "get_payment_status",
                {"customer_id": "CUS-1002"},
            ),
            make_final_response(
                "Your payment was completed successfully."
            ),
        ],
    )

    monkeypatch.setattr(
        orchestrator,
        "get_payment_status",
        lambda _db, _payload: PaymentResult(
            status="SUCCESS",
            payment_id="PAY-3002",
            customer_id="CUS-1002",
            transaction_reference="TXN-CD-3002",
            plan="PRO",
            amount=Decimal("29.00"),
            currency="USD",
            payment_status="SUCCESS",
            payment_date=datetime(
                2026, 8, 22, tzinfo=timezone.utc
            ).isoformat(),
        ),
    )

    result = orchestrator.run_agent(
        message=(
            "I want a refund for my successful Pro payment."
        ),
        customer_id="CUS-1002",
    )

    conversation_id = result["conversation_id"]

    try:
        proposal = result["action_proposal"]

        assert proposal is not None
        assert proposal["action_name"] == "request_refund_review"
        assert proposal["approval_status"] == "PENDING_APPROVAL"
        assert proposal["arguments"]["payment_id"] == "PAY-3002"

    finally:
        cleanup_conversation(
            conversation_id
        )


def test_pending_payment_does_not_create_action_proposal(
    monkeypatch,
) -> None:
    install_fake_client(
        monkeypatch,
        [
            make_tool_call_response(
                "get_payment_status",
                {"customer_id": "CUS-1004"},
            ),
            make_final_response(
                "The payment is still pending."
            ),
        ],
    )

    monkeypatch.setattr(
        orchestrator,
        "get_payment_status",
        lambda _db, _payload: PaymentResult(
            status="SUCCESS",
            payment_id="PAY-3004",
            customer_id="CUS-1004",
            transaction_reference="TXN-CD-3004",
            plan="PRO",
            amount=Decimal("29.00"),
            currency="USD",
            payment_status="PENDING",
            payment_date=datetime(
                2026, 8, 26, tzinfo=timezone.utc
            ).isoformat(),
        ),
    )

    result = orchestrator.run_agent(
        message="Is my Pro payment complete?",
        customer_id="CUS-1004",
    )

    conversation_id = result["conversation_id"]

    try:
        assert result["action_proposal"] is None

        with SessionLocal() as db:
            proposals = list(
                db.scalars(
                    select(
                        ActionProposal
                    ).where(
                        ActionProposal.run_id
                        == result["run_id"]
                    )
                ).all()
            )

            assert proposals == []

    finally:
        cleanup_conversation(
            conversation_id
        )

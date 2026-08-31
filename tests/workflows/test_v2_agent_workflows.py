from types import SimpleNamespace
from typing import Any

from google.genai import types
from sqlalchemy import delete, select

import app.agent.orchestrator as orchestrator
from app.agent.schemas import CustomerResult, PaymentResult, SubscriptionResult
from app.db.models import AgentRun, Conversation, Message, ToolExecution
from app.db.session import SessionLocal


class FakeModels:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = iter(responses)

    def generate_content(self, **_kwargs):
        return next(self.responses)


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def tool_call(name, args):
    call = SimpleNamespace(name=name, args=args)
    content = types.Content(
        role="model",
        parts=[types.Part.from_text(text=f"Calling {name}")],
    )
    return SimpleNamespace(
        function_calls=[call],
        candidates=[SimpleNamespace(content=content)],
        text=None,
    )


def final(text):
    return SimpleNamespace(function_calls=[], candidates=[], text=text)


def install(monkeypatch, responses):
    fake = FakeClient(responses)
    monkeypatch.setattr(orchestrator.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(orchestrator, "ensure_schema", lambda: None)
    monkeypatch.setattr(orchestrator.genai, "Client", lambda **_kwargs: fake)


def cleanup(conversation_id):
    with SessionLocal() as db:
        run_ids = list(
            db.scalars(
                select(AgentRun.run_id).where(
                    AgentRun.conversation_id == conversation_id
                )
            ).all()
        )
        if run_ids:
            db.execute(
                delete(ToolExecution).where(
                    ToolExecution.run_id.in_(run_ids)
                )
            )
        db.execute(delete(Message).where(Message.conversation_id == conversation_id))
        db.execute(delete(AgentRun).where(AgentRun.conversation_id == conversation_id))
        db.execute(delete(Conversation).where(Conversation.conversation_id == conversation_id))
        db.commit()


def test_general_no_tool_response_is_persisted(monkeypatch) -> None:
    install(monkeypatch, [final("That is outside SupportPilot's scope.")])
    result = orchestrator.run_agent(message="Who will win the World Cup?")
    try:
        assert result["intent"] == "general"
        assert result["response"]
    finally:
        cleanup(result["conversation_id"])


def test_subscription_single_tool_workflow(monkeypatch) -> None:
    install(
        monkeypatch,
        [
            tool_call("get_subscription", {"customer_id": "CUS-1001"}),
            final("You are on the Basic plan."),
        ],
    )
    monkeypatch.setattr(
        orchestrator,
        "get_subscription",
        lambda _db, payload: SubscriptionResult(
            status="SUCCESS",
            subscription_id="SUB-1001",
            customer_id=payload.customer_id,
            plan="BASIC",
            subscription_status="ACTIVE",
            requested_plan=None,
            last_sync_status="SUCCESS",
        ),
    )
    result = orchestrator.run_agent(
        message="What plan am I on?",
        customer_id="CUS-1001",
    )
    try:
        assert result["intent"] == "subscription"
        assert result["resolution"]["resolution_status"] == "RESOLVED"
    finally:
        cleanup(result["conversation_id"])


def test_payment_single_tool_workflow(monkeypatch) -> None:
    install(
        monkeypatch,
        [
            tool_call("get_payment_status", {"customer_id": "CUS-1007"}),
            final("Your Pro payment succeeded."),
        ],
    )
    monkeypatch.setattr(
        orchestrator,
        "get_payment_status",
        lambda _db, payload: PaymentResult(
            status="SUCCESS",
            payment_id="PAY-3007",
            customer_id=payload.customer_id,
            transaction_reference="TXN-CD-3007",
            plan="PRO",
            amount="29.00",
            currency="USD",
            payment_status="SUCCESS",
        ),
    )
    result = orchestrator.run_agent(
        message="Did my payment go through?",
        customer_id="CUS-1007",
    )
    try:
        assert result["intent"] == "payment"
        assert result["resolution"]["resolution_status"] == "RESOLVED"
    finally:
        cleanup(result["conversation_id"])


def test_flagship_three_tool_flow_escalates(monkeypatch) -> None:
    install(
        monkeypatch,
        [
            tool_call("get_customer", {"customer_id": "CUS-1007"}),
            tool_call("get_subscription", {"customer_id": "CUS-1007"}),
            tool_call("get_payment_status", {"customer_id": "CUS-1007"}),
            final("Your upgrade is complete."),
        ],
    )
    monkeypatch.setattr(
        orchestrator,
        "get_customer",
        lambda _db, payload: CustomerResult(
            status="SUCCESS",
            customer_id=payload.customer_id,
            name="Ananya Reddy",
            email="ananya@example.test",
            account_status="ACTIVE",
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "get_subscription",
        lambda _db, payload: SubscriptionResult(
            status="SUCCESS",
            subscription_id="SUB-1007",
            customer_id=payload.customer_id,
            plan="BASIC",
            subscription_status="ACTIVE",
            requested_plan="PRO",
            last_sync_status="FAILED",
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "get_payment_status",
        lambda _db, payload: PaymentResult(
            status="SUCCESS",
            payment_id="PAY-3007",
            customer_id=payload.customer_id,
            transaction_reference="TXN-CD-3007",
            plan="PRO",
            amount="29.00",
            currency="USD",
            payment_status="SUCCESS",
        ),
    )
    result = orchestrator.run_agent(
        message="I paid for Pro but still see Basic.",
        customer_id="CUS-1007",
    )
    try:
        assert result["resolution"]["resolution_status"] == "ESCALATION_REQUIRED"
        assert "not applied" in result["response"].lower()
    finally:
        cleanup(result["conversation_id"])


def test_payment_tool_failure_blocks_false_claim(monkeypatch) -> None:
    install(
        monkeypatch,
        [
            tool_call("get_payment_status", {"customer_id": "CUS-1007"}),
            final("Your payment definitely failed."),
        ],
    )

    def fail(_db, _payload):
        raise TimeoutError("billing unavailable")

    monkeypatch.setattr(orchestrator, "get_payment_status", fail)

    result = orchestrator.run_agent(
        message="Did my payment fail?",
        customer_id="CUS-1007",
    )
    try:
        assert result["resolution"]["resolution_status"] == "UNRESOLVED"
        assert "definitely failed" not in result["response"].lower()
    finally:
        cleanup(result["conversation_id"])


def test_max_step_limit_returns_safe_unresolved(monkeypatch) -> None:
    install(
        monkeypatch,
        [tool_call("get_customer", {"customer_id": "CUS-1007"})],
    )
    monkeypatch.setattr(
        orchestrator,
        "get_customer",
        lambda _db, payload: CustomerResult(
            status="SUCCESS",
            customer_id=payload.customer_id,
            name="Ananya Reddy",
            email="ananya@example.test",
            account_status="ACTIVE",
        ),
    )
    result = orchestrator.run_agent(
        message="Keep checking.",
        customer_id="CUS-1007",
        max_steps=1,
    )
    try:
        assert result["resolution"]["issue_type"] == "maximum_steps_reached"
        assert result["resolution"]["resolution_status"] == "UNRESOLVED"
    finally:
        cleanup(result["conversation_id"])

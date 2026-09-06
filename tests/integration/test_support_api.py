from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

import app.api.support as support_api
from app.db.models import Conversation, Message
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)


def test_chat_route_returns_mocked_agent_response(monkeypatch) -> None:
    monkeypatch.setattr(
        support_api,
        "run_agent",
        lambda **_kwargs: {
            "response": "You are on Basic.",
            "conversation_id": "conv-1",
            "run_id": "run-1",
            "intent": "subscription",
            "resolution": None,
            "trace": [],
        },
    )
    response = client.post(
        "/api/v1/support/chat",
        json={"message": "What plan am I on?", "customer_id": "CUS-1001"},
    )
    assert response.status_code == 200
    assert response.json()["run_id"] == "run-1"


def test_chat_rejects_empty_message() -> None:
    response = client.post("/api/v1/support/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_maps_runtime_error_to_503(monkeypatch) -> None:
    def fail(**_kwargs):
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    monkeypatch.setattr(support_api, "run_agent", fail)
    response = client.post("/api/v1/support/chat", json={"message": "Hello"})
    assert response.status_code == 503


def _make_conversation() -> str:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        conversation = Conversation(customer_id="CUS-1001")
        db.add(conversation)
        db.flush()
        db.add_all([
            Message(
                conversation_id=conversation.conversation_id,
                role="user",
                content="Hello",
                created_at=now,
            ),
            Message(
                conversation_id=conversation.conversation_id,
                role="assistant",
                content="Hi",
                created_at=now + timedelta(seconds=1),
            ),
        ])
        db.commit()
        return conversation.conversation_id


def _cleanup(conversation_id: str) -> None:
    with SessionLocal() as db:
        db.execute(delete(Message).where(Message.conversation_id == conversation_id))
        db.execute(delete(Conversation).where(Conversation.conversation_id == conversation_id))
        db.commit()


def test_history_route_restores_messages() -> None:
    conversation_id = _make_conversation()
    try:
        response = client.get(f"/api/v1/support/conversations/{conversation_id}")
        assert response.status_code == 200
        assert [m["role"] for m in response.json()["messages"]] == ["user", "assistant"]
    finally:
        _cleanup(conversation_id)


def test_history_route_rejects_wrong_customer() -> None:
    conversation_id = _make_conversation()
    try:
        response = client.get(
            f"/api/v1/support/conversations/{conversation_id}?customer_id=CUS-1002"
        )
        assert response.status_code == 403
    finally:
        _cleanup(conversation_id)


def test_history_route_returns_404_for_unknown_conversation() -> None:
    response = client.get("/api/v1/support/conversations/missing")
    assert response.status_code == 404


def test_history_response_includes_resolution_fields() -> None:
    conversation_id = _make_conversation()
    try:
        with SessionLocal() as db:
            conversation = db.get(Conversation, conversation_id)
            conversation.current_issue = "test_issue"
            conversation.resolution_status = "UNRESOLVED"
            db.commit()

        body = client.get(
            f"/api/v1/support/conversations/{conversation_id}"
        ).json()
        assert body["current_issue"] == "test_issue"
        assert body["resolution_status"] == "UNRESOLVED"
    finally:
        _cleanup(conversation_id)

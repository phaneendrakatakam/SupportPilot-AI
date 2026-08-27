from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_chat_route_calls_agent(
    monkeypatch,
) -> None:
    """
    Verify that the FastAPI chat endpoint
    forwards the request to the agent and
    returns persisted-run metadata.

    Gemini is mocked so pytest does not
    consume API quota.
    """

    def fake_run_agent(
        message: str,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict:
        assert message == (
            "What plan am I currently using?"
        )

        assert customer_id == "CUS-1001"

        assert conversation_id is None

        return {
            "response": (
                "You are currently on "
                "the Basic plan."
            ),
            "conversation_id": (
                "CONV-TEST-001"
            ),
            "run_id": "RUN-TEST-001",
            "intent": "subscription",
            "trace": [
                {
                    "step": 0,
                    "type": "request",
                    "customer_id": (
                        "CUS-1001"
                    ),
                    "message": (
                        "What plan am I "
                        "currently using?"
                    ),
                },
                {
                    "step": 1,
                    "type": "tool_call",
                    "tool": (
                        "get_subscription"
                    ),
                    "arguments": {
                        "customer_id": (
                            "CUS-1001"
                        )
                    },
                    "result_status": (
                        "SUCCESS"
                    ),
                    "latency_ms": 1.5,
                    "result": {
                        "status": (
                            "SUCCESS"
                        ),
                        "customer_id": (
                            "CUS-1001"
                        ),
                        "plan": "BASIC",
                    },
                },
                {
                    "step": 2,
                    "type": (
                        "final_response"
                    ),
                    "intent": (
                        "subscription"
                    ),
                    "response": (
                        "You are currently "
                        "on the Basic plan."
                    ),
                },
            ],
        }

    monkeypatch.setattr(
        "app.api.support.run_agent",
        fake_run_agent,
    )

    response = client.post(
        "/api/v1/support/chat",
        json={
            "message": (
                "What plan am I "
                "currently using?"
            ),
            "customer_id": (
                "CUS-1001"
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["response"] == (
        "You are currently on "
        "the Basic plan."
    )

    assert body["customer_id"] == (
        "CUS-1001"
    )

    assert body["conversation_id"] == (
        "CONV-TEST-001"
    )

    assert body["run_id"] == (
        "RUN-TEST-001"
    )

    assert body["intent"] == (
        "subscription"
    )

    assert body["trace"][1]["type"] == (
        "tool_call"
    )

    assert body["trace"][1]["tool"] == (
        "get_subscription"
    )


def test_chat_route_rejects_empty_message() -> None:
    """
    FastAPI/Pydantic should reject an empty
    customer message before invoking the agent.
    """

    response = client.post(
        "/api/v1/support/chat",
        json={
            "message": "",
            "customer_id": (
                "CUS-1001"
            ),
        },
    )

    assert response.status_code == 422


def test_chat_route_handles_unknown_conversation(
    monkeypatch,
) -> None:
    """
    Existing conversation IDs must not be
    silently invented by the API.
    """

    def fake_run_agent(
        message: str,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict:
        raise ValueError(
            "Conversation not found: missing-id"
        )

    monkeypatch.setattr(
        "app.api.support.run_agent",
        fake_run_agent,
    )

    response = client.post(
        "/api/v1/support/chat",
        json={
            "message": "Hello",
            "conversation_id": (
                "missing-id"
            ),
        },
    )

    assert response.status_code == 404
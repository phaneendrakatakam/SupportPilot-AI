import json

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.models import AgentRun, Conversation, ToolExecution
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)


def _create_run() -> tuple[str, str]:
    with SessionLocal() as db:
        conversation = Conversation(
            customer_id="CUS-1001",
            current_issue="subscription",
            resolution_status="RESOLVED",
        )
        db.add(conversation)
        db.flush()

        run = AgentRun(
            conversation_id=conversation.conversation_id,
            prompt_version="v2-multi-tool-2",
            intent="subscription",
            resolution_status="RESOLVED",
            request_message="What plan am I on?",
            issue_type="subscription",
            resolution_summary="Verified.",
            final_response="You are on Basic.",
            trace_json=json.dumps([{"step": 0, "type": "request"}]),
            latency_ms=12.5,
        )
        db.add(run)
        db.flush()

        db.add(
            ToolExecution(
                run_id=run.run_id,
                tool_name="get_customer",
                arguments_json=json.dumps({"customer_id": "CUS-1001"}),
                result_status="SUCCESS",
                latency_ms=1.2,
                result_json=json.dumps({
                    "status": "SUCCESS",
                    "email": "test@example.test",
                }),
            )
        )
        db.commit()
        return conversation.conversation_id, run.run_id


def _cleanup(conversation_id: str, run_id: str) -> None:
    with SessionLocal() as db:
        db.execute(delete(ToolExecution).where(ToolExecution.run_id == run_id))
        db.execute(delete(AgentRun).where(AgentRun.run_id == run_id))
        db.execute(delete(Conversation).where(Conversation.conversation_id == conversation_id))
        db.commit()


def test_debug_run_endpoint_returns_persisted_data() -> None:
    conversation_id, run_id = _create_run()
    try:
        response = client.get(f"/api/v1/debug/runs/{run_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == run_id
        assert body["final_response"] == "You are on Basic."
    finally:
        _cleanup(conversation_id, run_id)


def test_debug_masks_sensitive_email_field() -> None:
    conversation_id, run_id = _create_run()
    try:
        body = client.get(f"/api/v1/debug/runs/{run_id}").json()
        assert body["tool_executions"][0]["result"]["email"] == "[MASKED]"
    finally:
        _cleanup(conversation_id, run_id)


def test_debug_unknown_run_returns_404() -> None:
    response = client.get("/api/v1/debug/runs/missing-run")
    assert response.status_code == 404


def test_debug_lists_conversation_runs() -> None:
    conversation_id, run_id = _create_run()
    try:
        body = client.get(
            f"/api/v1/debug/conversations/{conversation_id}/runs"
        ).json()
        assert body["runs"][0]["run_id"] == run_id
    finally:
        _cleanup(conversation_id, run_id)

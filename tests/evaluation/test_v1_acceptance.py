from sqlalchemy import select, text

import app.agent.orchestrator as orchestrator

from app.config import settings
from app.db.models import Document
from app.db.session import SessionLocal


def test_v1_has_exactly_four_approved_tools() -> None:
    tool_names = {
        orchestrator.GET_CUSTOMER.name,
        orchestrator.GET_SUBSCRIPTION.name,
        orchestrator.GET_SERVICE_STATUS.name,
        orchestrator.SEARCH_KNOWLEDGE_BASE.name,
    }

    assert tool_names == {
        "get_customer",
        "get_subscription",
        "get_service_status",
        "search_knowledge_base",
    }


def test_seeded_customer_account_scenario() -> None:
    with SessionLocal() as db:
        result = orchestrator._execute_tool(
            db=db,
            tool_name="get_customer",
            arguments={
                "customer_id": "CUS-1003",
            },
        )

    assert result["status"] == "SUCCESS"
    assert result["customer_id"] == "CUS-1003"
    assert result["account_status"] == "SUSPENDED"


def test_seeded_subscription_upgrade_scenario() -> None:
    with SessionLocal() as db:
        result = orchestrator._execute_tool(
            db=db,
            tool_name="get_subscription",
            arguments={
                "customer_id": "CUS-1007",
            },
        )

    assert result["status"] == "SUCCESS"

    assert result["customer_id"] == "CUS-1007"

    assert result["plan"] == "BASIC"

    assert result["subscription_status"] == "ACTIVE"

    assert result["requested_plan"] == "PRO"

    assert result["last_sync_status"] == "FAILED"


def test_unknown_subscription_is_not_found() -> None:
    with SessionLocal() as db:
        result = orchestrator._execute_tool(
            db=db,
            tool_name="get_subscription",
            arguments={
                "customer_id": "CUS-9999",
            },
        )

    assert result["status"] == "NOT_FOUND"

    assert result["error"]

    assert (
        "No subscription record"
        in result["error"]
    )


def test_seeded_eu_service_incident() -> None:
    with SessionLocal() as db:
        result = orchestrator._execute_tool(
            db=db,
            tool_name="get_service_status",
            arguments={
                "service": "core",
                "region": "EU",
            },
        )

    assert result["status"] == "SUCCESS"

    incidents = result[
        "active_incidents"
    ]

    assert len(incidents) >= 1

    matching_incident = next(
        (
            incident
            for incident in incidents
            if (
                incident["incident_id"]
                == "INC-2001"
            )
        ),
        None,
    )

    assert matching_incident is not None

    assert (
        matching_incident["status"]
        == "ACTIVE"
    )

    assert (
        matching_incident["severity"]
        == "SEV2"
    )


def test_semantic_knowledge_base_is_ready() -> None:
    with SessionLocal() as db:
        result = db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_chunks,
                    COUNT(embedding) AS embedded_chunks,
                    MIN(
                        vector_dims(embedding)
                    ) AS min_dimensions,
                    MAX(
                        vector_dims(embedding)
                    ) AS max_dimensions
                FROM document_chunks
                """
            )
        ).mappings().one()

    assert (
        result["total_chunks"]
        > 0
    )

    assert (
        result["embedded_chunks"]
        == result["total_chunks"]
    )

    assert (
        result["min_dimensions"]
        == 768
    )

    assert (
        result["max_dimensions"]
        == 768
    )


def test_required_knowledge_documents_exist() -> None:
    expected_sources = {
        "refund_policy.md",
        "subscription_changes.md",
        "service_status.md",
        "support_scope.md",
    }

    with SessionLocal() as db:
        sources = set(
            db.scalars(
                select(
                    Document.source
                )
            ).all()
        )

    assert expected_sources.issubset(
        sources
    )


def test_pgvector_extension_is_enabled() -> None:
    with SessionLocal() as db:
        version = db.scalar(
            text(
                """
                SELECT extversion
                FROM pg_extension
                WHERE extname = 'vector'
                """
            )
        )

    assert version is not None


def test_v1_semantic_configuration() -> None:
    assert (
        settings.gemini_embedding_model
        == "gemini-embedding-2"
    )

    assert (
        settings.embedding_dimensions
        == 768
    )

    assert (
        orchestrator.PROMPT_VERSION
        == "v1-agent-foundation-3"
    )


def test_v1_evidence_guardrails_present() -> None:
    prompt = (
        orchestrator
        .SYSTEM_PROMPT
        .lower()
    )

    required_rules = [
        "candidate evidence",
        "similarity score",
        "missing documentation",
        "lifetime subscription",
        "bitcoin",
    ]

    for rule in required_rules:
        assert rule in prompt
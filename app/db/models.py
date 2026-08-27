from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


EMBEDDING_DIMENSIONS = 768


def utcnow() -> datetime:
    return datetime.now(
        timezone.utc
    )


def new_uuid() -> str:
    return str(
        uuid.uuid4()
    )


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    account_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    subscription_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    customer_id: Mapped[str] = mapped_column(
        ForeignKey(
            "customers.customer_id"
        ),
        nullable=False,
        index=True,
    )

    plan: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    requested_plan: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    last_sync_status: Mapped[str] = mapped_column(
        String(32),
        default="SUCCESS",
    )


class ServiceIncident(Base):
    __tablename__ = "service_incidents"

    incident_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    service: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
    )

    region: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    resolved_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Document(Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.document_id"
        ),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    embedding: Mapped[
        list[float] | None
    ] = mapped_column(
        Vector(
            EMBEDDING_DIMENSIONS
        ),
        nullable=True,
    )


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    customer_id: Mapped[
        str | None
    ] = mapped_column(
        ForeignKey(
            "customers.customer_id"
        ),
        nullable=True,
        index=True,
    )

    current_issue: Mapped[
        str | None
    ] = mapped_column(
        String(120),
        nullable=True,
    )

    resolution_status: Mapped[
        str | None
    ] = mapped_column(
        String(40),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey(
            "conversations.conversation_id"
        ),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    conversation_id: Mapped[
        str | None
    ] = mapped_column(
        ForeignKey(
            "conversations.conversation_id"
        ),
        nullable=True,
        index=True,
    )

    prompt_version: Mapped[str] = mapped_column(
        String(32),
        default="v1-day1",
    )

    intent: Mapped[
        str | None
    ] = mapped_column(
        String(80),
        nullable=True,
    )

    resolution_status: Mapped[
        str | None
    ] = mapped_column(
        String(40),
        nullable=True,
    )

    latency_ms: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    error: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    execution_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "agent_runs.run_id"
        ),
        nullable=False,
        index=True,
    )

    tool_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    arguments_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    result_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    latency_ms: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    result_json: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
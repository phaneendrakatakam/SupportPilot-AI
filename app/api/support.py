from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, select

from app.agent.orchestrator import ConversationCustomerMismatchError, run_agent
from app.agent.schemas import ResolutionDecision
from app.db.models import Conversation, Message
from app.db.schema import ensure_schema
from app.db.session import SessionLocal


router = APIRouter(prefix="/api/v1/support", tags=["support"])


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    customer_id: str | None = Field(default=None, max_length=32)
    conversation_id: str | None = Field(default=None, max_length=36)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str
    conversation_id: str
    run_id: str
    intent: str
    resolution: ResolutionDecision | None = None
    trace: list[dict]


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: str
    content: str
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    customer_id: str | None
    current_issue: str | None
    resolution_status: str | None
    messages: list[ConversationMessageResponse]


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = run_agent(
            message=payload.message,
            customer_id=payload.customer_id,
            conversation_id=payload.conversation_id,
        )
    except ConversationCustomerMismatchError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(**result)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationHistoryResponse,
)
def get_conversation_history(
    conversation_id: str,
    customer_id: str | None = Query(default=None),
) -> ConversationHistoryResponse:
    ensure_schema()

    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)

        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        if (
            customer_id
            and conversation.customer_id
            and customer_id != conversation.customer_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Customer does not match this conversation.",
            )

        role_order = case(
            (Message.role == "user", 0),
            (Message.role == "assistant", 1),
            else_=2,
        )

        messages = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at, role_order, Message.message_id)
            ).all()
        )

        return ConversationHistoryResponse(
            conversation_id=conversation.conversation_id,
            customer_id=conversation.customer_id,
            current_issue=conversation.current_issue,
            resolution_status=conversation.resolution_status,
            messages=[
                ConversationMessageResponse(
                    message_id=item.message_id,
                    role=item.role,
                    content=item.content,
                    created_at=item.created_at,
                )
                for item in messages
            ],
        )

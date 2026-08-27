from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.agent.orchestrator import run_agent


router = APIRouter(
    prefix="/api/v1/support",
    tags=["support"],
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    message: str = Field(
        min_length=1,
        max_length=4000,
    )

    customer_id: str | None = None

    conversation_id: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    response: str

    customer_id: str | None = None

    conversation_id: str

    run_id: str

    intent: str

    trace: list[
        dict[str, Any]
    ]


@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
) -> ChatResponse:
    """
    Send one customer message through the
    SupportPilot V1 agent.

    The request and resulting agent execution
    are persisted to PostgreSQL.
    """

    try:
        result = run_agent(
            message=request.message,
            customer_id=request.customer_id,
            conversation_id=(
                request.conversation_id
            ),
        )

    except ValueError as exc:
        message = str(exc)

        if message.startswith(
            "Conversation not found:"
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc

    except RuntimeError as exc:
        if "GEMINI_API_KEY" in str(exc):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini agent is "
                    "not configured."
                ),
            ) from exc

        raise HTTPException(
            status_code=500,
            detail=(
                "The support agent did not "
                "complete successfully."
            ),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "The support agent failed "
                "to process the request."
            ),
        ) from exc

    return ChatResponse(
        response=result["response"],
        customer_id=request.customer_id,
        conversation_id=(
            result["conversation_id"]
        ),
        run_id=result["run_id"],
        intent=result["intent"],
        trace=result["trace"],
    )
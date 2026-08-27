from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db.session import SessionLocal


router = APIRouter(
    tags=["health"],
)


@router.get("/health")
def health() -> dict[str, str]:
    """
    Basic local health check.

    Database connectivity is actively checked.

    Gemini is reported as configured/not-configured rather than making
    a real Gemini request every time /health is called. This avoids
    consuming API quota merely for a health check.
    """

    db_status = "up"

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))

    except SQLAlchemyError:
        db_status = "down"

    agent_status = (
        "configured"
        if settings.gemini_api_key
        else "not-configured"
    )

    return {
        "status": (
            "ok"
            if db_status == "up"
            else "degraded"
        ),
        "database": db_status,
        "agent": agent_status,
        "model": settings.gemini_model,
    }
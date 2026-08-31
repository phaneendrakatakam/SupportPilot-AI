from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db.session import SessionLocal


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    database_status = "up"

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_status = "down"

    return {
        "status": "ok" if database_status == "up" else "degraded",
        "database": database_status,
        "agent": "configured" if settings.gemini_api_key else "not_configured",
        "model": settings.gemini_model,
        "embedding_model": settings.gemini_embedding_model,
    }

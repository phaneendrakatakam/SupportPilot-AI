from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.support import router as support_router
from app.config import settings


BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "SupportPilot AI - local AI customer-support "
        "resolution agent for the fictional CloudDesk SaaS platform."
    ),
)


app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


app.include_router(
    health_router
)

app.include_router(
    support_router
)


@app.get(
    "/",
    include_in_schema=False,
)
def support_ui() -> FileResponse:
    """
    Serve the local SupportPilot customer-support UI.
    """

    return FileResponse(
        TEMPLATES_DIR / "index.html"
    )
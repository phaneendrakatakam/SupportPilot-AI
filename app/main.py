from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.debug import router as debug_router
from app.api.health import router as health_router
from app.api.support import router as support_router
from app.config import settings
from app.db.schema import ensure_schema


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "SupportPilot AI V2 - local multi-tool customer-support resolution agent."
    ),
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(health_router)
app.include_router(support_router)
app.include_router(debug_router)


@app.get("/", include_in_schema=False)
def support_ui() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/debug", include_in_schema=False)
def debug_ui() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "debug.html")

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from app.api.actions import router as actions_router
from app.api.debug import router as debug_router
from app.api.health import router as health_router
from app.api.support import router as support_router
from app.config import settings
from app.db.schema import ensure_schema
from app.security.operator import validate_operator


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

_OPERATOR_PATHS = (
    "/operations",
    "/debug",
    "/api/v1/actions",
    "/api/v1/debug",
)
security = HTTPBasic()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description=(
        "SupportPilot AI V3 - human-in-the-loop customer-support resolution agent."
    ),
    lifespan=lifespan,
)


@app.middleware("http")
async def operator_auth_middleware(request: Request, call_next):
    if settings.app_env == "production" and request.url.path.startswith(
        _OPERATOR_PATHS
    ):
        credentials: HTTPBasicCredentials = await security(request)
        validate_operator(
            credentials,
            settings.operator_username,
            settings.operator_password,
        )

    return await call_next(request)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(health_router)
app.include_router(support_router)
app.include_router(actions_router)
app.include_router(debug_router)


@app.get("/", include_in_schema=False)
def support_ui() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/operations", include_in_schema=False)
def operations_ui() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "operations.html")


@app.get("/debug", include_in_schema=False)
def debug_ui() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "debug.html")

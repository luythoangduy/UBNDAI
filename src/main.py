"""FastAPI entrypoint. Owner: Dev C (chỉ C sửa trực tiếp — TEAM_PLAN §4)."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI, Request
from fastapi.responses import Response
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.v1 import router as v1_router
from src.config import settings
from src.services.persistence import create_async_database

if settings.app_env == "production" and (
    settings.enable_demo_auth
    or len(settings.jwt_secret) < 32
    or settings.jwt_secret == "change-me"
):
    raise RuntimeError("Production requires a strong JWT_SECRET and demo auth disabled")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.database_persistence_enabled and settings.app_env != "production":
        database = create_async_database(settings.database_url)
        await database.create_schema()
        await database.engine.dispose()
    yield


app = FastAPI(title="TTHC Assist", version="0.1.0", lifespan=lifespan)
app.include_router(v1_router)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; img-src 'self' blob: data:; frame-src 'self' blob:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


class SPAStaticFiles(StaticFiles):
    """Serve index.html for client-side routes while preserving asset 404s."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and "." not in Path(path).name:
                return await super().get_response("index.html", scope)
            raise


frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
frontend_dist = frontend_dir / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="portal-assets")
    app.mount(
        "/citizen",
        SPAStaticFiles(directory=frontend_dist, html=True),
        name="citizen-portal",
    )
    app.mount(
        "/officer",
        SPAStaticFiles(directory=frontend_dist, html=True),
        name="officer-portal",
    )
elif frontend_dir.exists():
    app.mount(
        "/officer",
        SPAStaticFiles(directory=frontend_dir, html=True),
        name="officer-portal",
    )


@app.get("/health")
async def health() -> dict[str, str]:
    dialect = settings.database_url.split(":", 1)[0]
    return {
        "status": "ok",
        "database": dialect,
        "persistence": (
            "enabled" if settings.database_persistence_enabled else "disabled"
        ),
    }


__all__ = ["app"]

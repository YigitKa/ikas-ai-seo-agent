"""FastAPI application — serves the web API and React static files."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.dependencies import init_manager, shutdown_manager
from api.routers import products, seo, suggestions, settings, chat, llms, batch, reports, tasks
from core.prompt_store import ensure_prompt_files
from data import db
from data.db import close_pool as close_db_pool
from core.llms.service import llms_service
from core.services.daily_tracker import run_daily_snapshot

logger = logging.getLogger(__name__)

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


class SPAStaticFiles(StaticFiles):
    """Serve the React app for client-side routes that are not real files."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


async def _run_daily_snapshot_safe() -> None:
    """Run daily snapshot in background, never crash the server."""
    try:
        await run_daily_snapshot()
    except Exception:
        logger.warning("Daily score snapshot failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting ikas AI SEO Agent API")
    ensure_prompt_files()
    await db.init_db()
    await llms_service.bootstrap()
    init_manager()
    asyncio.create_task(_run_daily_snapshot_safe())
    yield
    await shutdown_manager()
    await close_db_pool()
    logger.info("Shut down ikas AI SEO Agent API")


app = FastAPI(
    title="ikas AI SEO Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ──────────────────────────────────────────────────────────────
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(seo.router, prefix="/api/seo", tags=["seo"])
app.include_router(suggestions.router, prefix="/api/suggestions", tags=["suggestions"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(llms.router, prefix="/api/llms", tags=["llms"])
app.include_router(batch.router, prefix="/api/batch", tags=["batch"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(chat.router, tags=["chat"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Serve React static files (production build) ─────────────────────────────
if WEB_DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=str(WEB_DIST), html=True), name="spa")

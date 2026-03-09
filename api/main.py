"""FastAPI application — serves the web API and React static files."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.dependencies import close_manager, get_manager
from api.routers import products, seo, suggestions, settings, chat
from data import db

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting ikas AI SEO Agent API")
    await db.init_db()
    get_manager()  # warm up singleton
    yield
    await close_manager()
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
app.include_router(chat.router, tags=["chat"])


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Serve React static files (production build) ─────────────────────────────
if WEB_DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=str(WEB_DIST), html=True), name="spa")

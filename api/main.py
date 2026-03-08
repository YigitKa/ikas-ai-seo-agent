"""FastAPI application — serves the web API and React static files."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.dependencies import get_manager
from api.routers import products, seo, suggestions, settings, chat

logger = logging.getLogger(__name__)

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting ikas AI SEO Agent API")
    get_manager()  # warm up singleton
    yield
    manager = get_manager()
    await manager.close()
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
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="spa")

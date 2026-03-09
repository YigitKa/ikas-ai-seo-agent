"""Shared FastAPI dependencies — global ProductManager singleton for REST endpoints."""

from __future__ import annotations

from core.product_manager import ProductManager

# Module-level singleton used by all REST endpoints.
# REST handlers are stateless (no conversation history, no per-user context),
# so sharing one instance is safe and avoids re-initialising the ikas OAuth
# token and AI client on every request.
#
# WebSocket connections must NOT use this singleton — each connection creates
# its own ProductManager so that chat history and product context are fully
# isolated per client (see api/routers/chat.py).
_manager: ProductManager | None = None


def get_manager() -> ProductManager:
    """Return the shared ProductManager singleton for REST endpoints."""
    global _manager
    if _manager is None:
        _manager = ProductManager()
    return _manager


async def close_manager() -> None:
    """Close and release the singleton (called from the FastAPI lifespan)."""
    global _manager
    if _manager is not None:
        await _manager.close()
        _manager = None

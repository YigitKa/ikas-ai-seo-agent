"""Shared FastAPI dependencies."""

from __future__ import annotations

from core.product_manager import ProductManager

# Application-scoped singleton for REST endpoints.
# Initialized via ``init_manager()`` during app startup and torn down via
# ``shutdown_manager()`` at shutdown.  WebSocket connections create their own
# per-connection ProductManager instances for chat state isolation.

_manager: ProductManager | None = None


def init_manager() -> ProductManager:
    """Create the global ProductManager singleton (called once at startup)."""
    global _manager
    _manager = ProductManager()
    return _manager


async def shutdown_manager() -> None:
    """Close the global ProductManager (called once at shutdown)."""
    global _manager
    if _manager is not None:
        await _manager.close()
        _manager = None


def get_manager() -> ProductManager:
    """Return the application-scoped ProductManager singleton."""
    assert _manager is not None, "ProductManager not initialized — call init_manager() first"
    return _manager

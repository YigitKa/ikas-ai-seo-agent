"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from core.product_manager import ProductManager


async def get_manager() -> AsyncIterator[ProductManager]:
    """Provide a fresh ProductManager for each request."""
    manager = ProductManager()
    try:
        yield manager
    finally:
        await manager.close()


async def close_manager() -> None:
    """Compatibility hook for app lifespan; no global manager is retained."""
    return None

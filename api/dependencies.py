"""Shared FastAPI dependencies — singleton ProductManager and config."""

from __future__ import annotations

from functools import lru_cache

from core.product_manager import ProductManager


@lru_cache(maxsize=1)
def get_manager() -> ProductManager:
    return ProductManager()

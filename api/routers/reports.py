"""Report API endpoints — daily SEO/GEO score tracking and trends."""

from __future__ import annotations

from fastapi import APIRouter, Query

from core.services.daily_tracker import run_daily_snapshot
from data import db

router = APIRouter()


@router.get("/store-trends")
async def store_trends(days: int = Query(90, ge=1, le=365)) -> list[dict]:
    """Store-wide daily score averages for the last N days."""
    return await db.get_store_daily_trends(days)


@router.get("/product-trends/{product_id}")
async def product_trends(
    product_id: str,
    days: int = Query(90, ge=1, le=365),
) -> list[dict]:
    """Daily score history for a single product."""
    return await db.get_product_daily_trends(product_id, days)


@router.get("/summary")
async def summary() -> dict:
    """First vs latest snapshot comparison with improvement deltas."""
    return await db.get_daily_summary()


@router.get("/top-improvers")
async def top_improvers(limit: int = Query(10, ge=1, le=50)) -> list[dict]:
    """Products with the biggest total_score improvement."""
    return await db.get_top_improvers(limit)


@router.get("/snapshot-dates")
async def snapshot_dates() -> list[str]:
    """List all snapshot dates."""
    return await db.get_snapshot_dates()


@router.get("/snapshot/{snapshot_date}")
async def snapshot_detail(snapshot_date: str) -> list[dict]:
    """All product scores for a specific snapshot date."""
    return await db.get_snapshot_products(snapshot_date)


@router.post("/take-snapshot")
async def take_snapshot() -> dict[str, str]:
    """Manually trigger a daily snapshot (idempotent)."""
    await run_daily_snapshot()
    return {"message": "Snapshot tamamlandi"}

"""Report API endpoints — daily SEO/GEO score tracking and trends."""

from __future__ import annotations

from typing import Optional

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


# ── Score change log ─────────────────────────────────────────────────────────


@router.get("/score-change-log")
async def score_change_log(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Query per-event score change log with optional filters."""
    return await db.get_score_change_log(
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        operation=operation,
        job_id=job_id,
        limit=limit,
        offset=offset,
    )


@router.get("/hourly-activity")
async def hourly_activity(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
) -> list[dict]:
    """Score change events grouped by hour-of-day (0-23)."""
    return await db.get_hourly_activity(start_date=start_date, end_date=end_date)


@router.get("/daily-activity")
async def daily_activity(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
) -> list[dict]:
    """Score change events grouped by calendar date."""
    return await db.get_daily_activity(start_date=start_date, end_date=end_date)


@router.get("/score-distribution")
async def score_distribution() -> list[dict]:
    """Current product score distribution in buckets."""
    return await db.get_score_distribution()


@router.get("/operation-metrics")
async def operation_metrics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
) -> list[dict]:
    """Per-operation-type success rate and avg delta."""
    return await db.get_operation_metrics(start_date=start_date, end_date=end_date)


@router.get("/score-change-summary")
async def score_change_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
) -> dict:
    """Aggregate stats for score change events in a date range."""
    return await db.get_score_change_summary(
        start_date=start_date,
        end_date=end_date,
    )

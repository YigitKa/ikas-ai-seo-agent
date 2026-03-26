"""Daily SEO/GEO score snapshot service.

Runs once per backend startup to capture a daily snapshot of all product scores.
"""

from __future__ import annotations

import logging
from datetime import date

from config.settings import get_config
from core.seo.analyzer import analyze_product
from data import db

logger = logging.getLogger(__name__)


async def run_daily_snapshot() -> None:
    """Score all cached products and save a daily snapshot.

    Idempotent — skips if today's snapshot already exists.
    """
    today = date.today().isoformat()

    if await db.has_daily_snapshot(today):
        logger.info("Daily snapshot for %s already exists, skipping", today)
        return

    products = await db.get_all_products()
    if not products:
        logger.info("No cached products found, skipping daily snapshot")
        return

    config = get_config()
    target_keywords = config.seo_target_keywords or []

    results: list[tuple] = []
    for product in products:
        try:
            score = analyze_product(product, target_keywords=target_keywords or None)
            results.append((product, score))
        except Exception:
            logger.warning("Failed to score product %s for daily snapshot", product.id, exc_info=True)

    if not results:
        logger.warning("No products scored successfully for daily snapshot")
        return

    await db.save_daily_snapshots(today, results)

    avg_score = sum(s.total_score for _, s in results) / len(results)
    logger.info(
        "Daily snapshot saved: %d products, avg score %.1f (date=%s)",
        len(results),
        avg_score,
        today,
    )

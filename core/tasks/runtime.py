from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.permissions import PermissionRule
from core.product_manager import ProductManager
from data import db

logger = logging.getLogger(__name__)


async def run_batch_analysis(
    job_id: str,
    product_ids: list[str],
    config: Any,
    manager: ProductManager,
) -> None:
    try:
        await manager.run_analysis(job_id, product_ids, config)
    except Exception as exc:
        logger.exception("Analysis failed for job %s", job_id)
        await db.update_batch_job(job_id, status="failed", error=str(exc))


def launch_batch_analysis(
    job_id: str,
    product_ids: list[str],
    config: Any,
    manager: ProductManager,
) -> asyncio.Task:
    return asyncio.create_task(run_batch_analysis(job_id, product_ids, config, manager))


async def run_batch_apply(
    job_id: str,
    config: Any,
    manager: ProductManager,
    permission_rules: list[PermissionRule] | None = None,
) -> None:
    try:
        await manager.apply_batch_job(job_id, config, permission_rules=permission_rules)
    except Exception as exc:
        logger.exception("Batch apply %s failed", job_id)
        await db.update_batch_job(job_id, status="failed", error=str(exc))


def launch_batch_apply(
    job_id: str,
    config: Any,
    manager: ProductManager,
    permission_rules: list[PermissionRule] | None = None,
) -> asyncio.Task:
    return asyncio.create_task(run_batch_apply(job_id, config, manager, permission_rules=permission_rules))

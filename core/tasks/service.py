from __future__ import annotations

from typing import Any

from core.llms.service import llms_service
from core.permissions import build_runtime_allow_rule
from core.product_manager import ProductManager
from core.tasks.runtime import launch_batch_analysis, launch_batch_apply
from data import db


ACTIVE_BATCH_STATUSES = {"analyzing", "running"}
RESUMABLE_BATCH_STATUSES = {"cancelled", "failed", "stopped"}
RESUMABLE_LLMS_STATUSES = {"paused", "queued", "stopped", "failed", "cancelled"}


async def get_task_status(task_id: str):
    return await db.get_task(task_id)


async def stop_task(task_id: str) -> None:
    task = await db.get_task(task_id)
    if task is None:
        raise ValueError("Task not found")

    if task.type == "llms_generation":
        await llms_service.stop_job()
        job = await db.get_llms_job(task_id)
        if job is not None and job.status not in {"completed", "failed"}:
            await db.update_llms_job_status(task_id, "stopped")
        return

    if task.type == "batch_job":
        job = await db.get_batch_job(task_id)
        if job is None:
            raise ValueError("Batch job not found")
        if job["status"] not in ACTIVE_BATCH_STATUSES:
            raise RuntimeError("Task is not running")
        await db.update_batch_job(task_id, status="cancelled")
        return

    raise RuntimeError(f"Unsupported task type: {task.type}")


async def cancel_task(task_id: str) -> None:
    await stop_task(task_id)


async def resume_task(task_id: str, manager: ProductManager) -> Any:
    task = await db.get_task(task_id)
    if task is None:
        raise ValueError("Task not found")

    if task.type == "llms_generation":
        if task.status not in RESUMABLE_LLMS_STATUSES:
            raise RuntimeError("Task cannot be resumed from its current status")
        return await llms_service.resume_job(task_id)

    if task.type == "batch_job":
        return await _resume_batch_job(task, manager)

    raise RuntimeError(f"Unsupported task type: {task.type}")


async def retry_task(task_id: str, manager: ProductManager) -> Any:
    task = await db.get_task(task_id)
    if task is None:
        raise ValueError("Task not found")

    if task.type == "llms_generation":
        return await llms_service.retry_job(task_id)

    if task.type == "batch_job":
        return await _resume_batch_job(task, manager, force_retry=True)

    raise RuntimeError(f"Unsupported task type: {task.type}")


async def _resume_batch_job(task, manager: ProductManager, *, force_retry: bool = False) -> dict[str, Any]:
    job = await db.get_batch_job(task.id)
    if job is None:
        raise ValueError("Batch job not found")
    if not force_retry and job["status"] not in RESUMABLE_BATCH_STATUSES:
        raise RuntimeError("Task cannot be resumed from its current status")

    payload = dict(task.payload)
    config = payload.get("config", job["config"])
    stage = str(payload.get("stage") or "analysis")

    if stage == "apply":
        await db.update_batch_job(task.id, status="running", error=None)
        await db.patch_task_payload(task.id, {"stage": "apply"})
        launch_batch_apply(
            task.id,
            config,
            manager,
            permission_rules=[
                build_runtime_allow_rule(
                    "bulk_apply",
                    description="The unified task runtime resumed a batch apply job.",
                )
            ],
        )
        refreshed = await db.get_batch_job(task.id)
        if refreshed is None:
            raise RuntimeError("Batch job missing after resume")
        return refreshed

    product_ids = list(payload.get("product_ids") or [])
    if not product_ids:
        raise RuntimeError("Task payload does not include product IDs")

    items = await db.get_batch_items(task.id)
    seen_product_ids = {item["product_id"] for item in items}
    remaining_ids = [product_id for product_id in product_ids if product_id not in seen_product_ids]
    if not remaining_ids:
        raise RuntimeError("No remaining products to analyze for this task")

    await db.update_batch_job(task.id, status="analyzing", error=None)
    await db.patch_task_payload(task.id, {"stage": "analysis"})
    launch_batch_analysis(task.id, remaining_ids, config, manager)
    refreshed = await db.get_batch_job(task.id)
    if refreshed is None:
        raise RuntimeError("Batch job missing after resume")
    return refreshed

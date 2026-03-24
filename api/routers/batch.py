"""Batch SEO optimization endpoints — job lifecycle, calibration, rollback."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.dependencies import get_manager
from api.schemas import (
    BatchConfig,
    BatchItemDecisionRequest,
    BatchItemResponse,
    BatchJobDetailResponse,
    BatchJobResponse,
    BatchStatsResponse,
    StartBatchRequest,
)
from core.product_manager import ProductManager
from data import db

logger = logging.getLogger(__name__)
router = APIRouter()


def _job_to_response(job: dict) -> BatchJobResponse:
    return BatchJobResponse(**job)


def _item_to_response(item: dict) -> BatchItemResponse:
    return BatchItemResponse(**item)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=BatchStatsResponse)
async def get_batch_stats() -> BatchStatsResponse:
    """Aggregate stats for the Command Center dashboard."""
    stats = await db.get_batch_stats()
    active = BatchJobResponse(**stats["active_job"]) if stats["active_job"] else None
    return BatchStatsResponse(
        total_jobs=stats["total_jobs"],
        total_processed=stats["total_processed"],
        avg_score_improvement=stats["avg_score_improvement"],
        active_job=active,
    )


# ── Job CRUD ──────────────────────────────────────────────────────────────────

@router.get("/jobs", response_model=list[BatchJobResponse])
async def list_batch_jobs() -> list[BatchJobResponse]:
    jobs = await db.list_batch_jobs()
    return [_job_to_response(j) for j in jobs]


@router.post("/jobs", response_model=BatchJobResponse)
async def create_batch_job(
    body: StartBatchRequest,
    manager: ProductManager = Depends(get_manager),
) -> BatchJobResponse:
    """Create a new batch job. Starts calibration or runs directly based on flag."""
    job_id = str(uuid4())
    config_json = body.config.model_dump_json()
    await db.create_batch_job(job_id, config_json)

    if body.run_calibration_first:
        await db.update_batch_job(job_id, status="calibrating")
        # Run calibration in background — creates batch_items with status='calibration'
        asyncio.create_task(
            _run_calibration_task(job_id, body.config, manager)
        )
    else:
        await db.update_batch_job(job_id, status="running")
        asyncio.create_task(
            _run_batch_task(job_id, body.config, manager)
        )

    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=500, detail="Job creation failed")
    return _job_to_response(job)


@router.get("/jobs/{job_id}", response_model=BatchJobDetailResponse)
async def get_batch_job(job_id: str) -> BatchJobDetailResponse:
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    items = await db.get_batch_items(job_id)
    return BatchJobDetailResponse(
        job=_job_to_response(job),
        items=[_item_to_response(i) for i in items],
    )


@router.get("/jobs/{job_id}/stream")
async def stream_batch_job(job_id: str) -> StreamingResponse:
    """SSE stream for real-time batch progress updates."""
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_processed = -1
        for _ in range(600):  # max 10 min at 1s polling
            current = await db.get_batch_job(job_id)
            if not current:
                break
            if current["processed_count"] != last_processed:
                last_processed = current["processed_count"]
                yield f"data: {json.dumps({'type': 'progress', 'job': current})}\n\n"
            if current["status"] in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'type': 'completed', 'job': current})}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Job lifecycle ─────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/start", response_model=BatchJobResponse)
async def start_full_batch_run(
    job_id: str,
    manager: ProductManager = Depends(get_manager),
) -> BatchJobResponse:
    """Start the full batch run after calibration is approved."""
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "calibrating":
        raise HTTPException(status_code=400, detail="Job is not in calibration state")

    config = BatchConfig(**job["config"])
    await db.update_batch_job(job_id, status="running")
    asyncio.create_task(_run_batch_task(job_id, config, manager))

    updated = await db.get_batch_job(job_id)
    return _job_to_response(updated)


@router.post("/jobs/{job_id}/stop", response_model=BatchJobResponse)
async def stop_batch_job(job_id: str) -> BatchJobResponse:
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("calibrating", "running"):
        raise HTTPException(status_code=400, detail="Job is not running")
    await db.update_batch_job(job_id, status="cancelled")
    updated = await db.get_batch_job(job_id)
    return _job_to_response(updated)


# ── Rollback ──────────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/rollback")
async def rollback_batch_job(
    job_id: str,
    manager: ProductManager = Depends(get_manager),
) -> dict:
    """Roll back all applied items in this batch job."""
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    items = await db.get_batch_items(job_id)
    applied = [i for i in items if i["status"] == "applied" and i["has_rollback"]]
    rolled_back = 0
    for item in applied:
        data = await db.get_batch_item_rollback_data(item["id"])
        if data:
            product_id = data.pop("product_id")
            success = await manager.rollback_product(product_id, data)
            if success:
                await db.update_batch_item(item["id"], status="rolled_back")
                rolled_back += 1
    return {"rolled_back": rolled_back, "total": len(applied)}


@router.post("/items/{item_id}/rollback")
async def rollback_batch_item(
    item_id: int,
    manager: ProductManager = Depends(get_manager),
) -> dict:
    """Roll back a single batch item to its original product data."""
    data = await db.get_batch_item_rollback_data(item_id)
    if not data:
        raise HTTPException(status_code=404, detail="Item not found or no rollback data")
    product_id = data.pop("product_id")
    success = await manager.rollback_product(product_id, data)
    if success:
        await db.update_batch_item(item_id, status="rolled_back")
    return {"ok": success, "product_id": product_id}


# ── Calibration item decisions ────────────────────────────────────────────────

@router.patch("/items/{item_id}", response_model=BatchItemResponse)
async def update_batch_item_decision(
    item_id: int,
    body: BatchItemDecisionRequest,
) -> BatchItemResponse:
    """Approve, reject, or revise a calibration sample item."""
    if body.decision not in ("approved", "rejected", "revised"):
        raise HTTPException(status_code=400, detail="decision must be approved, rejected, or revised")

    status = "approved" if body.decision in ("approved", "revised") else "rejected"
    await db.update_batch_item(item_id, status=status)
    item = await db.get_batch_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return _item_to_response(item)


# ── Background task helpers ───────────────────────────────────────────────────

async def _run_calibration_task(
    job_id: str,
    config: BatchConfig,
    manager: ProductManager,
) -> None:
    """Background task: pick sample products, generate rewrites, save as calibration items."""
    try:
        items = await manager.run_calibration(job_id, config)
        await db.update_batch_job(
            job_id,
            total_count=len(items),
            status="calibrating",
        )
        logger.info("Calibration complete for job %s: %d samples", job_id, len(items))
    except Exception as exc:
        logger.exception("Calibration failed for job %s", job_id)
        await db.update_batch_job(job_id, status="failed", error=str(exc))


async def _run_batch_task(
    job_id: str,
    config: BatchConfig,
    manager: ProductManager,
) -> None:
    """Background task: process all matching products and save results."""
    try:
        await manager.run_batch_job(job_id, config)
    except Exception as exc:
        logger.exception("Batch job %s failed", job_id)
        await db.update_batch_job(job_id, status="failed", error=str(exc))

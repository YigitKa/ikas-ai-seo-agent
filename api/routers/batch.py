"""Batch SEO optimization endpoints — select → analyze → review → apply."""

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
    """Aggregate stats for the dashboard."""
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
    """Create a new batch job with explicit product_ids.  Starts analysis in background."""
    if not body.product_ids:
        raise HTTPException(status_code=400, detail="En az bir ürün seçmelisiniz.")

    job_id = str(uuid4())
    config_json = body.config.model_dump_json()
    await db.create_batch_job(job_id, config_json)
    await db.update_batch_job(job_id, status="analyzing", total_count=len(body.product_ids))

    asyncio.create_task(
        _run_analysis_task(job_id, body.product_ids, body.config, manager)
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
    """SSE stream for real-time progress updates."""
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
            if current["status"] in ("analyzed", "completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'type': 'completed', 'job': current})}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Job lifecycle ─────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/apply", response_model=BatchJobResponse)
async def apply_batch_job(
    job_id: str,
    manager: ProductManager = Depends(get_manager),
) -> BatchJobResponse:
    """Apply approved suggestions to ikas (transitions analyzed → running)."""
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "analyzed":
        raise HTTPException(status_code=400, detail="İş henüz analiz aşamasında değil.")

    config = BatchConfig(**job["config"])
    await db.update_batch_job(job_id, status="running")
    asyncio.create_task(_run_apply_task(job_id, config, manager))

    updated = await db.get_batch_job(job_id)
    return _job_to_response(updated)


@router.post("/jobs/{job_id}/stop", response_model=BatchJobResponse)
async def stop_batch_job(job_id: str) -> BatchJobResponse:
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("analyzing", "running"):
        raise HTTPException(status_code=400, detail="İş çalışmıyor.")
    await db.update_batch_job(job_id, status="cancelled")
    updated = await db.get_batch_job(job_id)
    return _job_to_response(updated)


@router.delete("/jobs/{job_id}")
async def delete_batch_job_endpoint(job_id: str):
    deleted = await db.delete_batch_job(job_id)
    if not deleted:
        raise HTTPException(status_code=400, detail="Aktif veya bulunamayan iş silinemez.")
    return {"ok": True}


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


@router.post("/items/{item_id}/regenerate", response_model=BatchItemResponse)
async def regenerate_batch_item(
    item_id: int,
    manager: ProductManager = Depends(get_manager),
) -> BatchItemResponse:
    try:
        item = await manager.regenerate_batch_item(item_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _item_to_response(item)


@router.post("/items/{item_id}/fields/{field_key}/regenerate", response_model=BatchItemResponse)
async def regenerate_batch_item_field(
    item_id: int,
    field_key: str,
    manager: ProductManager = Depends(get_manager),
) -> BatchItemResponse:
    try:
        item = await manager.regenerate_batch_item_field(item_id, field_key)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return _item_to_response(item)


# ── Item decisions ────────────────────────────────────────────────────────────

@router.patch("/items/{item_id}", response_model=BatchItemResponse)
async def update_batch_item_decision(
    item_id: int,
    body: BatchItemDecisionRequest,
    manager: ProductManager = Depends(get_manager),
) -> BatchItemResponse:
    """Approve or reject an analyzed item."""
    try:
        item = await manager.update_batch_item_decision(
            item_id,
            body.decision,
            body.revised_data,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return _item_to_response(item)


@router.post("/items/bulk-decision")
async def bulk_update_item_decisions(
    body: dict,
) -> dict:
    """Approve or reject multiple items at once."""
    item_ids: list[int] = body.get("item_ids", [])
    decision: str = body.get("decision", "")
    if not item_ids or decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="item_ids and decision (approved/rejected) required")
    status = decision
    updated = await db.bulk_update_batch_item_status(item_ids, status)
    return {"updated": updated}


# ── Background task helpers ───────────────────────────────────────────────────

async def _run_analysis_task(
    job_id: str,
    product_ids: list[str],
    config: BatchConfig,
    manager: ProductManager,
) -> None:
    """Background: generate AI suggestions for each selected product."""
    try:
        await manager.run_analysis(job_id, product_ids, config)
    except Exception as exc:
        logger.exception("Analysis failed for job %s", job_id)
        await db.update_batch_job(job_id, status="failed", error=str(exc))


async def _run_apply_task(
    job_id: str,
    config: BatchConfig,
    manager: ProductManager,
) -> None:
    """Background: apply approved suggestions to ikas."""
    try:
        await manager.apply_batch_job(job_id, config)
    except Exception as exc:
        logger.exception("Batch apply %s failed", job_id)
        await db.update_batch_job(job_id, status="failed", error=str(exc))

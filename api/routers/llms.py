from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.llms.service import llms_service
from data import db

router = APIRouter()


async def _enrich_entries(entries):
    if not entries:
        return []
    product_ids = [e.product_id for e in entries]
    products_map = await db.get_products_by_ids(product_ids)
    enriched = []
    for entry in entries:
        product = products_map.get(entry.product_id)
        enriched.append(
            {
                "product_id": entry.product_id,
                "product_name": product.name if product else "",
                "category": product.category if product else None,
                "summary": entry.summary,
                "status": entry.status,
                "updated_at": entry.updated_at.isoformat(),
            }
        )
    return enriched


@router.get("/status")
async def llms_status() -> dict:
    counts = await db.get_llms_dashboard_counts()
    job = await db.get_llms_latest_job(statuses=["running", "paused", "queued", "completed"])
    latest_done = await db.get_llms_recent_entries("done", limit=8)
    pending_products = await db.get_llms_unprocessed_products(limit=12)
    return {
        "job": job.model_dump() if job else None,
        "counts": counts,
        "current": (
            {
                "product_id": llms_service.current_product.id,
                "product_name": llms_service.current_product.name,
                "category": llms_service.current_product.category,
            }
            if llms_service.current_product
            else None
        ),
        "latest_processed": await _enrich_entries(latest_done),
        "unprocessed": [
            {
                "product_id": p.id,
                "product_name": p.name,
                "category": p.category,
            }
            for p in pending_products
        ],
    }


@router.post("/start")
async def llms_start() -> dict:
    try:
        job = await llms_service.start_new_job()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job.model_dump()}


@router.post("/resume")
async def llms_resume() -> dict:
    try:
        job = await llms_service.resume_job()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job.model_dump()}


@router.post("/pause")
async def llms_pause() -> dict:
    await llms_service.pause_job()
    job = await db.get_llms_latest_job()
    if job:
        await db.update_llms_job_status(job.id, "paused")
    return {"message": "llms.txt isleri durduruldu"}


@router.post("/stop")
async def llms_stop() -> dict:
    await llms_service.stop_job()
    job = await db.get_llms_latest_job()
    if job:
        await db.update_llms_job_status(job.id, "stopped")
    return {"message": "llms.txt isleri tamamen durduruldu"}


@router.get("/processed")
async def llms_processed(limit: int | None = None) -> dict:
    entries = await db.get_llms_entries("done", limit=limit)
    return {"items": await _enrich_entries(entries)}


@router.get("/pending")
async def llms_pending(limit: int | None = None) -> dict:
    products = await db.get_llms_unprocessed_products(limit=limit or 200)
    return {
        "items": [
            {
                "product_id": p.id,
                "product_name": p.name,
                "category": p.category,
                "summary": "",
                "status": "pending",
                "updated_at": "",
            }
            for p in products
        ]
    }


@router.post("/regenerate/{product_id}")
async def llms_regenerate(product_id: str) -> dict:
    try:
        entry = await llms_service.regenerate_product(product_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": entry}

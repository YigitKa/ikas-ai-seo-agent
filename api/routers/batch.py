"""Batch SEO optimization endpoints — select → analyze → review → apply."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.dependencies import get_manager
from api.permissions import raise_http_for_permission
from api.schemas import (
    BatchConfig,
    BatchItemDecisionRequest,
    BatchItemResponse,
    BatchJobDetailResponse,
    BatchJobResponse,
    BatchStatsResponse,
    StartBatchRequest,
)
from core.permissions import PermissionDecisionError, build_runtime_allow_rule
from core.product_manager import ProductManager
from core.tasks.runtime import launch_batch_analysis, launch_batch_apply
from data import db

router = APIRouter()

BATCH_STAGE_LABELS = {
    "queued": "Hazirlaniyor",
    "analyzing": "Analiz",
    "awaiting_review": "Inceleme Bekleniyor",
    "awaiting_approval": "Onay Bekleniyor",
    "applying": "Uygulama",
    "rolling_back": "Geri Alma",
    "completed": "Tamamlandi",
    "completed_with_errors": "Hata ile Tamamlandi",
    "failed": "Hata",
    "cancelled": "Durduruldu",
}

BATCH_STAGE_MESSAGES = {
    "queued": "Islem siraya alindi.",
    "analyzing": "Urunler analiz ediliyor.",
    "awaiting_review": "Analiz tamamlandi. Inceleme bekleniyor.",
    "awaiting_approval": "Kullanici onayi bekleniyor.",
    "applying": "Onaylanan urunler IKAS'a yaziliyor.",
    "rolling_back": "Degisiklikler geri aliniyor.",
    "completed": "Toplu islem tamamlandi.",
    "completed_with_errors": "Toplu islem bitti, bazi urunlerde hata var.",
    "failed": "Islem hata ile sonlandi.",
    "cancelled": "Islem kullanici tarafindan durduruldu.",
}

TERMINAL_BATCH_STATUSES = {"analyzed", "completed", "completed_with_errors", "failed", "cancelled"}


def _build_summary_counts(job: dict) -> dict[str, int]:
    total = int(job.get("total_count") or 0)
    succeeded = int(job.get("processed_count") or 0)
    skipped = int(job.get("skipped_count") or 0)
    failed = int(job.get("failed_count") or 0)
    processed = succeeded + skipped + failed
    if total > 0:
        processed = min(processed, total)
    return {
        "total": total,
        "processed": processed,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "retried": 0,
        "remaining": max(total - processed, 0),
    }


def _default_feedback_stage(job_status: str, task_stage: str) -> str:
    if job_status == "analyzing":
        return "analyzing"
    if job_status == "analyzed":
        return "awaiting_review"
    if job_status == "running":
        return "applying" if task_stage == "apply" else "analyzing"
    if job_status == "completed":
        return "completed"
    if job_status == "completed_with_errors":
        return "completed_with_errors"
    if job_status == "failed":
        return "failed"
    if job_status == "cancelled":
        return "cancelled"
    if task_stage == "apply":
        return "applying"
    if task_stage == "analysis":
        return "queued"
    return "queued"


def _default_next_action_hints(stage: str, job_status: str) -> list[str]:
    if stage == "awaiting_review":
        return [
            "Analiz sonucunu inceleyin.",
            "Hazir oldugunuzda toplu apply islemini baslatin.",
        ]
    if stage in {"completed_with_errors", "failed", "cancelled"}:
        return [
            "Detay ekranindan hatali veya atlanan urunleri inceleyin.",
            "Gerekirse islemi tekrar calistirin.",
        ]
    if stage == "completed":
        return [
            "Uygulanan urunleri detay ekranindan kontrol edin.",
            "Gerekirse rollback kullanin.",
        ]
    if job_status in {"analyzing", "running"}:
        return [
            "Canli ilerlemeyi takip edin.",
            "Gerekirse islemi durdurun.",
        ]
    return []


def _normalize_feedback_item(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        "product_id": str(raw.get("product_id") or ""),
        "product_name": str(raw.get("product_name") or ""),
        "item_status": str(raw.get("item_status") or ""),
        "reason_code": raw.get("reason_code"),
        "user_message": raw.get("user_message"),
        "at": raw.get("at"),
    }


def _normalize_feedback_event(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        "sequence": int(raw.get("sequence") or 0),
        "type": str(raw.get("type") or ""),
        "stage": str(raw.get("stage") or ""),
        "label": str(raw.get("label") or ""),
        "message": str(raw.get("message") or ""),
        "at": raw.get("at"),
        "product_id": raw.get("product_id"),
        "product_name": raw.get("product_name"),
        "item_status": raw.get("item_status"),
        "reason_code": raw.get("reason_code"),
        "user_message": raw.get("user_message"),
        "retryable": raw.get("retryable"),
    }


def _build_feedback(job: dict, task: Any | None) -> dict[str, Any]:
    payload = dict(task.payload) if task is not None else {}
    raw_feedback = payload.get("feedback") if isinstance(payload.get("feedback"), dict) else {}
    task_stage = str(payload.get("stage") or "")
    stage = str(raw_feedback.get("stage") or _default_feedback_stage(str(job.get("status") or ""), task_stage))
    summary_counts = _build_summary_counts(job)
    raw_counts = raw_feedback.get("summary_counts") if isinstance(raw_feedback.get("summary_counts"), dict) else {}
    summary_counts["retried"] = int(raw_counts.get("retried") or 0)
    sequence = int(raw_feedback.get("sequence") or 0)
    current_item = _normalize_feedback_item(raw_feedback.get("current_item"))
    last_completed_item = _normalize_feedback_item(raw_feedback.get("last_completed_item"))
    latest_event = _normalize_feedback_event(raw_feedback.get("latest_event"))
    recent_events = [
        event
        for event in (_normalize_feedback_event(item) for item in raw_feedback.get("recent_events", []))
        if event is not None
    ]
    heartbeat_at = task.heartbeat_at.isoformat() if task and task.heartbeat_at else None
    last_event_at = raw_feedback.get("last_event_at") or heartbeat_at or job.get("updated_at")
    if latest_event is None and recent_events:
        latest_event = recent_events[0]
    if latest_event is None and last_event_at:
        latest_event = {
            "sequence": sequence,
            "type": "status",
            "stage": stage,
            "label": BATCH_STAGE_LABELS.get(stage, stage),
            "message": str(raw_feedback.get("status_message") or BATCH_STAGE_MESSAGES.get(stage, "")),
            "at": last_event_at,
            "product_id": None,
            "product_name": None,
            "item_status": None,
            "reason_code": None,
            "user_message": None,
            "retryable": None,
        }
    return {
        "stage": stage,
        "stage_label": str(raw_feedback.get("stage_label") or BATCH_STAGE_LABELS.get(stage, stage)),
        "status_message": str(raw_feedback.get("status_message") or BATCH_STAGE_MESSAGES.get(stage, "")),
        "sequence": sequence,
        "warning_count": int(raw_feedback.get("warning_count") or (summary_counts["skipped"] + summary_counts["failed"])),
        "eta_seconds": raw_feedback.get("eta_seconds"),
        "last_event_at": last_event_at,
        "stalled_since": raw_feedback.get("stalled_since"),
        "heartbeat_at": heartbeat_at,
        "summary_counts": summary_counts,
        "current_item": current_item,
        "last_completed_item": last_completed_item,
        "latest_event": latest_event,
        "recent_events": recent_events,
        "next_action_hints": list(raw_feedback.get("next_action_hints") or _default_next_action_hints(stage, str(job.get("status") or ""))),
    }


async def _job_to_response(job: dict) -> BatchJobResponse:
    task = await db.get_task(str(job.get("task_id") or job["id"]))
    return BatchJobResponse(**job, feedback=_build_feedback(job, task))


def _item_to_response(item: dict) -> BatchItemResponse:
    return BatchItemResponse(**item)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=BatchStatsResponse)
async def get_batch_stats() -> BatchStatsResponse:
    """Aggregate stats for the dashboard."""
    stats = await db.get_batch_stats()
    active = await _job_to_response(stats["active_job"]) if stats["active_job"] else None
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
    return list(await asyncio.gather(*(_job_to_response(job) for job in jobs)))


@router.post("/jobs", response_model=BatchJobResponse)
async def create_batch_job(
    body: StartBatchRequest,
    manager: ProductManager = Depends(get_manager),
) -> BatchJobResponse:
    """Create a new batch job with explicit product_ids.  Starts analysis in background."""
    if not body.product_ids:
        raise HTTPException(status_code=400, detail="En az bir ürün seçmelisiniz.")

    try:
        manager.validate_skill_for_flow(body.config.skill_slug, "batch")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = str(uuid4())
    config_json = body.config.model_dump_json()
    await db.create_batch_job(
        job_id,
        config_json,
        task_payload={
            "config": body.config.model_dump(),
            "product_ids": list(body.product_ids),
            "stage": "analysis",
        },
    )
    await db.update_batch_job(job_id, status="analyzing", total_count=len(body.product_ids))
    launch_batch_analysis(job_id, body.product_ids, body.config, manager)

    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=500, detail="Job creation failed")
    return await _job_to_response(job)


@router.get("/jobs/{job_id}", response_model=BatchJobDetailResponse)
async def get_batch_job(job_id: str) -> BatchJobDetailResponse:
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    items = await db.get_batch_items(job_id)
    return BatchJobDetailResponse(
        job=await _job_to_response(job),
        items=[_item_to_response(i) for i in items],
    )


@router.get("/jobs/{job_id}/stream")
async def stream_batch_job(job_id: str) -> StreamingResponse:
    """SSE stream for real-time progress updates."""
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_snapshot = ""
        for _ in range(600):  # max 10 min at 1s polling
            current = await db.get_batch_job(job_id)
            if not current:
                break
            response_model = await _job_to_response(current)
            response_payload = response_model.model_dump(mode="json")
            snapshot = json.dumps(response_payload, sort_keys=True, ensure_ascii=False)
            if snapshot != last_snapshot:
                last_snapshot = snapshot
                event_type = "completed" if current["status"] in TERMINAL_BATCH_STATUSES else "progress"
                yield f"data: {json.dumps({'type': event_type, 'job': response_payload}, ensure_ascii=False)}\n\n"
            if current["status"] in TERMINAL_BATCH_STATUSES:
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
    await db.patch_task_payload(job_id, {"stage": "apply", "config": config.model_dump()})
    await db.update_batch_job(job_id, status="running")
    launch_batch_apply(
        job_id,
        config,
        manager,
        permission_rules=[
            build_runtime_allow_rule(
                "bulk_apply",
                description="The batch apply endpoint was invoked explicitly by the user.",
            )
        ],
    )

    updated = await db.get_batch_job(job_id)
    if updated is None:
        raise HTTPException(status_code=500, detail="Job update failed")
    return await _job_to_response(updated)


@router.post("/jobs/{job_id}/stop", response_model=BatchJobResponse)
async def stop_batch_job(job_id: str) -> BatchJobResponse:
    job = await db.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("analyzing", "running"):
        raise HTTPException(status_code=400, detail="İş çalışmıyor.")
    await db.update_batch_job(job_id, status="cancelled")
    updated = await db.get_batch_job(job_id)
    if updated is None:
        raise HTTPException(status_code=500, detail="Job update failed")
    return await _job_to_response(updated)


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
            try:
                success = await manager.rollback_product(
                    product_id,
                    data,
                    permission_rules=[
                        build_runtime_allow_rule(
                            "rollback",
                            description="The batch rollback endpoint was invoked explicitly by the user.",
                        )
                    ],
                )
            except PermissionDecisionError as exc:
                raise_http_for_permission(exc)
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
    try:
        success = await manager.rollback_product(
            product_id,
            data,
            permission_rules=[
                build_runtime_allow_rule(
                    "rollback",
                    description="The batch item rollback endpoint was invoked explicitly by the user.",
                )
            ],
        )
    except PermissionDecisionError as exc:
        raise_http_for_permission(exc)
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


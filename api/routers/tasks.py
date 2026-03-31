from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_manager
from api.schemas import TaskListResponse, TaskResponse
from core.product_manager import ProductManager
from core.tasks import cancel_task, get_task_status, resume_task, retry_task, stop_task
from data import db

router = APIRouter()


async def _require_task_response(task_id: str):
    return await db.get_task(task_id)


@router.get("", response_model=TaskListResponse)
async def list_unified_tasks(
    task_type: list[str] | None = Query(default=None, alias="type"),
    status: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TaskListResponse:
    tasks = await db.list_tasks(task_types=task_type, statuses=status, limit=limit, offset=offset)
    return TaskListResponse(items=[TaskResponse.from_record(task) for task in tasks])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_unified_task(task_id: str) -> TaskResponse:
    task = await _require_task_response(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(task)


@router.post("/{task_id}/stop", response_model=TaskResponse)
async def stop_unified_task(task_id: str) -> TaskResponse:
    try:
        await stop_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    task = await _require_task_response(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(task)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_unified_task(task_id: str) -> TaskResponse:
    try:
        await cancel_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    task = await _require_task_response(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(task)


@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_unified_task(
    task_id: str,
    manager: ProductManager = Depends(get_manager),
) -> TaskResponse:
    try:
        await resume_task(task_id, manager)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    task = await _require_task_response(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(task)


@router.post("/{task_id}/retry", response_model=TaskResponse)
async def retry_unified_task(
    task_id: str,
    manager: ProductManager = Depends(get_manager),
) -> TaskResponse:
    try:
        await retry_task(task_id, manager)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    task = await _require_task_response(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_record(task)

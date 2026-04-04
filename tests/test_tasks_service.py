"""Tests for core/tasks/service.py — task lifecycle management."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import data.db as db_mod
from core.tasks.service import (
    get_task_status,
    stop_task,
    cancel_task,
    resume_task,
    retry_task,
    ACTIVE_BATCH_STATUSES,
    RESUMABLE_BATCH_STATUSES,
    RESUMABLE_LLMS_STATUSES,
)


def _setup_db(monkeypatch, tmp_path, name="tasks_svc.db"):
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / name)
    asyncio.run(db_mod.init_db())


def _make_manager():
    mgr = MagicMock()
    mgr.validate_skill_for_flow = MagicMock()
    return mgr


def _create_batch_job(job_id, status="analyzing", product_ids=None):
    asyncio.run(db_mod.create_batch_job(
        job_id,
        json.dumps({}),
        task_payload={
            "config": {},
            "product_ids": product_ids or ["p1", "p2"],
            "stage": "analysis",
        },
    ))
    asyncio.run(db_mod.update_batch_job(job_id, status=status, total_count=2))


# ── get_task_status ───────────────────────────────────────────────────────────

def test_get_task_status_missing_returns_none(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "gs_miss.db")
    result = asyncio.run(get_task_status("nonexistent"))
    assert result is None


def test_get_task_status_existing_task(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "gs_ok.db")
    _create_batch_job("task-1", status="analyzing")

    result = asyncio.run(get_task_status("task-1"))
    assert result is not None
    assert result.id == "task-1"


# ── stop_task ─────────────────────────────────────────────────────────────────

def test_stop_task_missing_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "stop_miss.db")
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(stop_task("ghost"))


def test_stop_batch_job_not_running_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "stop_not_run.db")
    _create_batch_job("idle-job", status="completed")

    with pytest.raises(RuntimeError, match="not running"):
        asyncio.run(stop_task("idle-job"))


def test_stop_active_batch_job(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "stop_active.db")
    _create_batch_job("active-job", status="analyzing")

    asyncio.run(stop_task("active-job"))

    task = asyncio.run(db_mod.get_task("active-job"))
    assert task is not None
    assert task.status == "cancelled"


def test_stop_llms_task(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "stop_llms.db")
    job = asyncio.run(db_mod.create_llms_job(["p1"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "running"))

    with patch("core.tasks.service.llms_service") as mock_svc:
        mock_svc.stop_job = AsyncMock()
        asyncio.run(stop_task(job.id))
        mock_svc.stop_job.assert_awaited_once()


# ── cancel_task ───────────────────────────────────────────────────────────────

def test_cancel_task_is_alias_for_stop(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "cancel.db")
    _create_batch_job("cancel-job", status="running")

    asyncio.run(cancel_task("cancel-job"))

    task = asyncio.run(db_mod.get_task("cancel-job"))
    assert task is not None
    assert task.status == "cancelled"


# ── resume_task ───────────────────────────────────────────────────────────────

def test_resume_task_missing_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "res_miss.db")
    manager = _make_manager()
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(resume_task("ghost", manager))


def test_resume_llms_task_from_paused(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "res_llms.db")
    job = asyncio.run(db_mod.create_llms_job(["p1"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "paused"))

    manager = _make_manager()
    with patch("core.tasks.service.llms_service") as mock_svc:
        mock_svc.resume_job = AsyncMock(return_value=job)
        result = asyncio.run(resume_task(job.id, manager))
        mock_svc.resume_job.assert_awaited_once_with(job.id)
    assert result is not None


def test_resume_llms_task_wrong_status_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "res_llms_bad.db")
    job = asyncio.run(db_mod.create_llms_job(["p1"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "completed"))

    manager = _make_manager()
    with patch("core.tasks.service.llms_service"):
        with pytest.raises(RuntimeError, match="cannot be resumed"):
            asyncio.run(resume_task(job.id, manager))


def test_resume_batch_task_from_cancelled(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "res_batch.db")
    _create_batch_job("res-batch", status="cancelled")

    manager = _make_manager()
    with patch("core.tasks.service.launch_batch_analysis") as mock_launch:
        result = asyncio.run(resume_task("res-batch", manager))
        mock_launch.assert_called_once()
    assert result is not None


def test_resume_batch_task_wrong_status_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "res_batch_bad.db")
    _create_batch_job("res-batch-bad", status="completed")

    manager = _make_manager()
    with pytest.raises(RuntimeError, match="cannot be resumed"):
        asyncio.run(resume_task("res-batch-bad", manager))


def test_resume_batch_task_apply_stage(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "res_apply.db")
    _create_batch_job("apply-job", status="cancelled")
    asyncio.run(db_mod.patch_task_payload("apply-job", {"stage": "apply"}))

    manager = _make_manager()
    with patch("core.tasks.service.launch_batch_apply") as mock_apply:
        result = asyncio.run(resume_task("apply-job", manager))
        mock_apply.assert_called_once()
    assert result is not None


# ── retry_task ────────────────────────────────────────────────────────────────

def test_retry_task_missing_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "retry_miss.db")
    manager = _make_manager()
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(retry_task("ghost", manager))


def test_retry_llms_task(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "retry_llms.db")
    job = asyncio.run(db_mod.create_llms_job(["p1"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "failed"))

    manager = _make_manager()
    with patch("core.tasks.service.llms_service") as mock_svc:
        mock_svc.retry_job = AsyncMock(return_value=job)
        result = asyncio.run(retry_task(job.id, manager))
        mock_svc.retry_job.assert_awaited_once_with(job.id)


def test_retry_batch_task(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "retry_batch.db")
    _create_batch_job("retry-b", status="failed")

    manager = _make_manager()
    with patch("core.tasks.service.launch_batch_analysis") as mock_launch:
        result = asyncio.run(retry_task("retry-b", manager))
        mock_launch.assert_called_once()
    assert result is not None


# ── Constants validation ──────────────────────────────────────────────────────

def test_active_batch_statuses_are_frozenset_or_set():
    assert isinstance(ACTIVE_BATCH_STATUSES, (set, frozenset))
    assert "analyzing" in ACTIVE_BATCH_STATUSES


def test_resumable_batch_statuses_include_cancelled():
    assert "cancelled" in RESUMABLE_BATCH_STATUSES
    assert "failed" in RESUMABLE_BATCH_STATUSES


def test_resumable_llms_statuses_include_paused():
    assert "paused" in RESUMABLE_LLMS_STATUSES
    assert "stopped" in RESUMABLE_LLMS_STATUSES

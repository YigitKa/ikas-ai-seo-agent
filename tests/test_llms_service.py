"""Tests for core/llms/service.py — LlmsService orchestration."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import data.db as db_mod
from core.models import Product


def _setup_db(monkeypatch, tmp_path, name="llms_svc.db"):
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_path / name)
    asyncio.run(db_mod.init_db())


def _make_service(monkeypatch):
    """Create a LlmsService with mocked AI client and prompt files."""
    with (
        patch("core.llms.service.get_config"),
        patch("core.llms.service.ensure_prompt_files"),
        patch("core.llms.service.create_ai_client") as mock_create,
    ):
        mock_ai = MagicMock()
        mock_ai.summarize_for_llms.return_value = "Product summary text"
        mock_ai.last_usage = {"input": 100, "output": 50}
        mock_ai.cancel_active_request = MagicMock()
        mock_create.return_value = mock_ai

        from core.llms.service import LlmsService
        svc = LlmsService()
        return svc, mock_ai


# ── start_new_job ─────────────────────────────────────────────────────────────

def test_start_new_job_no_products_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "start_no_prod.db")
    svc, _ = _make_service(monkeypatch)

    with pytest.raises(RuntimeError, match="urun"):
        asyncio.run(svc.start_new_job())


def test_start_new_job_creates_job(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "start_ok.db")
    asyncio.run(db_mod.save_product(Product(id="p1", name="Test")))

    svc, _ = _make_service(monkeypatch)

    # Cancel immediately so we don't run the full worker loop
    async def _run():
        svc._stop_event.set()  # Signal stop before task runs
        job = await svc.start_new_job()
        return job

    # Patch _start_worker to just set job_id without spawning real task
    async def _fake_start_worker(job_id, resume=False):
        svc._job_id = job_id

    svc._start_worker = _fake_start_worker
    job = asyncio.run(svc.start_new_job())
    assert job is not None
    assert job.id is not None


def test_start_new_job_raises_when_already_running(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "start_running.db")
    asyncio.run(db_mod.save_product(Product(id="p1", name="Test")))

    svc, _ = _make_service(monkeypatch)

    # Simulate a running task
    loop = asyncio.new_event_loop()
    svc._task = loop.create_future()  # not done

    with pytest.raises(RuntimeError, match="calisan"):
        asyncio.run(svc.start_new_job())

    loop.close()


# ── resume_job ────────────────────────────────────────────────────────────────

def test_resume_job_no_paused_job_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "resume_none.db")
    svc, _ = _make_service(monkeypatch)

    with pytest.raises(RuntimeError):
        asyncio.run(svc.resume_job())


def test_resume_job_finds_paused_job(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "resume_ok.db")
    job = asyncio.run(db_mod.create_llms_job(["p1"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "paused"))

    svc, _ = _make_service(monkeypatch)

    async def _fake_start_worker(job_id, resume=False):
        svc._job_id = job_id

    svc._start_worker = _fake_start_worker
    result = asyncio.run(svc.resume_job())
    assert result is not None
    assert result.id == job.id


# ── pause_job / stop_job ──────────────────────────────────────────────────────

def test_pause_job_sets_stop_event(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "pause.db")
    svc, _ = _make_service(monkeypatch)

    # Create a fake running task
    async def _fake_coro():
        await asyncio.sleep(10)

    loop = asyncio.new_event_loop()
    svc._task = loop.create_task(_fake_coro())

    async def _run():
        await svc.pause_job()

    loop.run_until_complete(_run())
    assert svc._stop_event.is_set()
    assert svc._stop_reason == "paused"
    svc._task.cancel()
    loop.close()


def test_stop_job_sets_stop_reason(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "stop.db")
    svc, _ = _make_service(monkeypatch)

    async def _fake_coro():
        await asyncio.sleep(10)

    loop = asyncio.new_event_loop()
    svc._task = loop.create_task(_fake_coro())

    async def _run():
        await svc.stop_job()

    loop.run_until_complete(_run())
    assert svc._stop_event.is_set()
    assert svc._stop_reason == "stopped"
    svc._task.cancel()
    loop.close()


def test_pause_when_no_task_is_noop(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "pause_noop.db")
    svc, _ = _make_service(monkeypatch)
    # No running task — should not raise
    asyncio.run(svc.pause_job())


# ── current_product property ──────────────────────────────────────────────────

def test_current_product_initially_none(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "current.db")
    svc, _ = _make_service(monkeypatch)
    assert svc.current_product is None


# ── reload_ai_client ──────────────────────────────────────────────────────────

def test_reload_ai_client(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "reload.db")
    svc, mock_ai = _make_service(monkeypatch)

    with (
        patch("core.llms.service.get_config"),
        patch("core.llms.service.create_ai_client") as mock_create2,
    ):
        new_ai = MagicMock()
        mock_create2.return_value = new_ai
        svc.reload_ai_client()
        assert svc._ai is new_ai


# ── retry_job ─────────────────────────────────────────────────────────────────

def test_retry_job_not_found_raises(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "retry_miss.db")
    svc, _ = _make_service(monkeypatch)

    with pytest.raises(RuntimeError, match="bulunamadi"):
        asyncio.run(svc.retry_job("nonexistent-id"))


def test_retry_job_resets_failed_entries(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "retry_ok.db")
    job = asyncio.run(db_mod.create_llms_job(["p1", "p2"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "failed"))

    svc, _ = _make_service(monkeypatch)

    async def _fake_start_worker(job_id, resume=False):
        svc._job_id = job_id

    svc._start_worker = _fake_start_worker
    result = asyncio.run(svc.retry_job(job.id))
    assert result is not None

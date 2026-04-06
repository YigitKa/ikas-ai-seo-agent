"""Tests for api/routers/batch.py — batch job lifecycle endpoints."""

import asyncio
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import data.db as db_mod
from api.dependencies import get_manager
from api.main import app


# ── Test DB setup ─────────────────────────────────────────────────────────────

def _setup_api_db(tmp_path, name):
    """Set up a fresh SQLite DB for API tests.

    Resets the connection pool so both the test setup code and the TestClient
    use direct aiosqlite connections against the same temp path.
    """
    db_mod.DB_PATH = tmp_path / name
    # Reset pool state so every call falls back to direct aiosqlite.connect()
    db_mod._pool = None
    db_mod._pool_initialized = False
    asyncio.run(db_mod.init_db())
    # Reset pool again — init_db may have created one; we want fallback mode
    db_mod._pool = None
    db_mod._pool_initialized = False


# ── Stub ProductManager ───────────────────────────────────────────────────────

class _StubManager:
    def validate_skill_for_flow(self, skill_slug, flow):
        pass  # always valid


def _override_manager(stub=None):
    s = stub or _StubManager()
    app.dependency_overrides[get_manager] = lambda: s
    return s


def _clear():
    app.dependency_overrides.clear()


# ── /api/batch/stats ──────────────────────────────────────────────────────────

def test_batch_stats_returns_structure(tmp_path):
    _setup_api_db(tmp_path, "b_stats.db")
    _override_manager()
    client = TestClient(app)
    try:
        resp = client.get("/api/batch/stats")
    finally:
        _clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "total_jobs" in body
    assert "total_processed" in body
    assert "avg_score_improvement" in body
    assert "active_job" in body


# ── /api/batch/jobs GET ───────────────────────────────────────────────────────

def test_list_batch_jobs_empty(tmp_path):
    _setup_api_db(tmp_path, "b_list.db")
    _override_manager()
    client = TestClient(app)
    try:
        resp = client.get("/api/batch/jobs")
    finally:
        _clear()

    assert resp.status_code == 200
    assert resp.json() == []


# ── /api/batch/jobs POST ──────────────────────────────────────────────────────

def test_create_batch_job_no_products_returns_400(tmp_path):
    _setup_api_db(tmp_path, "b_no_prod.db")
    _override_manager()
    client = TestClient(app)
    try:
        resp = client.post("/api/batch/jobs", json={
            "product_ids": [],
            "config": {"skill_slug": "seo_basic"},
        })
    finally:
        _clear()

    assert resp.status_code == 400
    assert "ürün" in resp.json()["detail"].lower() or "urun" in resp.json()["detail"].lower()


def test_create_batch_job_invalid_skill_returns_400(tmp_path):
    _setup_api_db(tmp_path, "b_bad_skill.db")

    class _BadSkillManager:
        def validate_skill_for_flow(self, skill_slug, flow):
            raise ValueError("Unknown skill")

    _override_manager(_BadSkillManager())
    client = TestClient(app)
    try:
        with patch("core.tasks.runtime.launch_batch_analysis"):
            resp = client.post("/api/batch/jobs", json={
                "product_ids": ["p1"],
                "config": {"skill_slug": "nonexistent"},
            })
    finally:
        _clear()

    assert resp.status_code == 400


def test_create_batch_job_success(tmp_path):
    _setup_api_db(tmp_path, "b_success.db")
    _override_manager()
    client = TestClient(app)
    try:
        with patch("core.tasks.runtime.launch_batch_analysis"):
            resp = client.post("/api/batch/jobs", json={
                "product_ids": ["prod-1", "prod-2"],
                "config": {"skill_slug": "seo_basic"},
            })
    finally:
        _clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert body["total_count"] == 2
    assert body["feedback"]["stage"] in {"queued", "analyzing"}
    assert "summary_counts" in body["feedback"]


# ── /api/batch/jobs/{job_id} GET ─────────────────────────────────────────────

def test_get_batch_job_not_found(tmp_path):
    _setup_api_db(tmp_path, "b_miss.db")
    _override_manager()
    client = TestClient(app)
    try:
        resp = client.get("/api/batch/jobs/nonexistent-job-id")
    finally:
        _clear()

    assert resp.status_code == 404


def test_get_batch_job_existing(tmp_path):
    _setup_api_db(tmp_path, "b_exist.db")
    asyncio.run(db_mod.create_batch_job(
        "known-job",
        json.dumps({"skill_slug": "seo_basic"}),
        task_payload={"config": {}, "product_ids": ["p1"], "stage": "analysis"},
    ))

    _override_manager()
    client = TestClient(app)
    try:
        resp = client.get("/api/batch/jobs/known-job")
    finally:
        _clear()

    assert resp.status_code == 200
    # BatchJobDetailResponse wraps in {"job": {...}, "items": [...]}
    body = resp.json()
    assert body["job"]["id"] == "known-job"
    assert body["job"]["feedback"]["stage"] == "queued"
    assert body["job"]["feedback"]["summary_counts"]["total"] == 0


# ── /api/batch/jobs/{job_id} DELETE ──────────────────────────────────────────

def test_delete_batch_job_not_found_returns_400(tmp_path):
    """Missing jobs return 400 (endpoint combines missing + active into one error)."""
    _setup_api_db(tmp_path, "b_del_miss.db")
    _override_manager()
    client = TestClient(app)
    try:
        resp = client.delete("/api/batch/jobs/ghost-job")
    finally:
        _clear()

    assert resp.status_code == 400


def test_delete_batch_job_running_returns_400(tmp_path):
    """Running jobs cannot be deleted — returns 400."""
    _setup_api_db(tmp_path, "b_del_run.db")
    asyncio.run(db_mod.create_batch_job(
        "running-job",
        json.dumps({}),
        task_payload={"config": {}, "product_ids": ["p1"], "stage": "apply"},
    ))
    asyncio.run(db_mod.update_batch_job("running-job", status="running"))

    _override_manager()
    client = TestClient(app)
    try:
        resp = client.delete("/api/batch/jobs/running-job")
    finally:
        _clear()

    assert resp.status_code == 400


# ── /api/batch/jobs/{job_id}/stop POST ───────────────────────────────────────

def test_stop_batch_job_not_found(tmp_path):
    _setup_api_db(tmp_path, "b_stop_miss.db")
    _override_manager()
    client = TestClient(app)
    try:
        resp = client.post("/api/batch/jobs/ghost/stop")
    finally:
        _clear()

    assert resp.status_code == 404


def test_stop_batch_job_returns_cancelled_feedback(tmp_path):
    _setup_api_db(tmp_path, "b_stop_ok.db")
    asyncio.run(db_mod.create_batch_job(
        "stop-job",
        json.dumps({}),
        task_payload={"config": {}, "product_ids": ["p1"], "stage": "analysis"},
    ))
    asyncio.run(db_mod.update_batch_job("stop-job", status="analyzing", total_count=1))

    _override_manager()
    client = TestClient(app)
    try:
        resp = client.post("/api/batch/jobs/stop-job/stop")
    finally:
        _clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["feedback"]["stage"] == "cancelled"


# ── /api/batch/jobs/{job_id}/rollback POST ────────────────────────────────────

def test_rollback_batch_job_not_found(tmp_path):
    _setup_api_db(tmp_path, "b_rollback.db")
    _override_manager()
    client = TestClient(app)
    try:
        resp = client.post("/api/batch/jobs/ghost/rollback")
    finally:
        _clear()

    assert resp.status_code == 404

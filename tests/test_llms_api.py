"""Tests for api/routers/llms.py — llms.txt generation lifecycle endpoints."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import data.db as db_mod
from api.main import app


def _setup_api_db(tmp_path, name):
    db_mod.DB_PATH = tmp_path / name
    db_mod._pool = None
    db_mod._pool_initialized = False
    asyncio.run(db_mod.init_db())
    db_mod._pool = None
    db_mod._pool_initialized = False


# ── /api/llms/status ──────────────────────────────────────────────────────────

def test_llms_status_empty_store(tmp_path):
    _setup_api_db(tmp_path, "llms_status.db")
    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.current_product = None
        client = TestClient(app)
        resp = client.get("/api/llms/status")

    assert resp.status_code == 200
    body = resp.json()
    assert "job" in body
    assert "counts" in body
    assert "current" in body
    assert body["current"] is None


def test_llms_status_with_current_product(tmp_path):
    _setup_api_db(tmp_path, "llms_status_cur.db")
    from core.models import Product
    current = Product(id="cp-1", name="Active Product", category="Elektronik")

    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.current_product = current
        client = TestClient(app)
        resp = client.get("/api/llms/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["current"]["product_id"] == "cp-1"
    assert body["current"]["product_name"] == "Active Product"


# ── /api/llms/start ───────────────────────────────────────────────────────────

def test_llms_start_no_products_raises_400(tmp_path):
    _setup_api_db(tmp_path, "llms_start_empty.db")
    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.start_new_job = AsyncMock(side_effect=RuntimeError("No products"))
        client = TestClient(app)
        resp = client.post("/api/llms/start")

    assert resp.status_code == 400
    assert "No products" in resp.json()["detail"]


def test_llms_start_while_running_returns_400(tmp_path):
    _setup_api_db(tmp_path, "llms_start_run.db")
    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.start_new_job = AsyncMock(side_effect=RuntimeError("Job already running"))
        client = TestClient(app)
        resp = client.post("/api/llms/start")

    assert resp.status_code == 400


def test_llms_start_success(tmp_path):
    _setup_api_db(tmp_path, "llms_start_ok.db")
    job = asyncio.run(db_mod.create_llms_job(["p1", "p2"], options={}))

    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.start_new_job = AsyncMock(return_value=job)
        client = TestClient(app)
        resp = client.post("/api/llms/start")

    assert resp.status_code == 200
    assert "job" in resp.json()


# ── /api/llms/resume ──────────────────────────────────────────────────────────

def test_llms_resume_no_paused_job_returns_400(tmp_path):
    _setup_api_db(tmp_path, "llms_resume_none.db")
    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.resume_job = AsyncMock(side_effect=RuntimeError("Nothing to resume"))
        client = TestClient(app)
        resp = client.post("/api/llms/resume")

    assert resp.status_code == 400


def test_llms_resume_success(tmp_path):
    _setup_api_db(tmp_path, "llms_resume_ok.db")
    job = asyncio.run(db_mod.create_llms_job(["p1"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "paused"))
    refreshed = asyncio.run(db_mod.get_llms_job(job.id))

    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.resume_job = AsyncMock(return_value=refreshed)
        client = TestClient(app)
        resp = client.post("/api/llms/resume")

    assert resp.status_code == 200
    assert "job" in resp.json()


# ── /api/llms/pause ───────────────────────────────────────────────────────────

def test_llms_pause(tmp_path):
    _setup_api_db(tmp_path, "llms_pause.db")
    job = asyncio.run(db_mod.create_llms_job(["p1"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "running"))

    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.pause_job = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/llms/pause")

    assert resp.status_code == 200
    assert "durduruldu" in resp.json()["message"]


# ── /api/llms/stop ────────────────────────────────────────────────────────────

def test_llms_stop(tmp_path):
    _setup_api_db(tmp_path, "llms_stop.db")
    job = asyncio.run(db_mod.create_llms_job(["p1"], options={}))
    asyncio.run(db_mod.update_llms_job_status(job.id, "running"))

    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.stop_job = AsyncMock()
        client = TestClient(app)
        resp = client.post("/api/llms/stop")

    assert resp.status_code == 200
    assert "durduruldu" in resp.json()["message"]


# ── /api/llms/processed ──────────────────────────────────────────────────────

def test_llms_processed_empty(tmp_path):
    _setup_api_db(tmp_path, "llms_proc.db")
    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.current_product = None
        client = TestClient(app)
        resp = client.get("/api/llms/processed")

    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ── /api/llms/pending ────────────────────────────────────────────────────────

def test_llms_pending_empty(tmp_path):
    _setup_api_db(tmp_path, "llms_pend_empty.db")
    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.current_product = None
        client = TestClient(app)
        resp = client.get("/api/llms/pending")

    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_llms_pending_with_products(tmp_path):
    _setup_api_db(tmp_path, "llms_pend_prods.db")
    from core.models import Product
    asyncio.run(db_mod.save_product(Product(id="pend-1", name="Product 1")))
    asyncio.run(db_mod.save_product(Product(id="pend-2", name="Product 2")))

    with patch("api.routers.llms.llms_service") as mock_svc:
        mock_svc.current_product = None
        client = TestClient(app)
        resp = client.get("/api/llms/pending")

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    ids = {i["product_id"] for i in items}
    assert "pend-1" in ids
    assert "pend-2" in ids

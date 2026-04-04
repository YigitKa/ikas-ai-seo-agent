"""Tests for api/routers/reports.py — score history, trends, and snapshot endpoints."""

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


# ── /api/reports/store-trends ─────────────────────────────────────────────────

def test_store_trends_empty(tmp_path):
    _setup_api_db(tmp_path, "trends.db")
    client = TestClient(app)
    resp = client.get("/api/reports/store-trends")
    assert resp.status_code == 200
    assert resp.json() == []


def test_store_trends_with_days_param(tmp_path):
    _setup_api_db(tmp_path, "trends2.db")
    client = TestClient(app)
    resp = client.get("/api/reports/store-trends?days=30")
    assert resp.status_code == 200


def test_store_trends_invalid_days_returns_422(tmp_path):
    _setup_api_db(tmp_path, "trends3.db")
    client = TestClient(app)
    resp = client.get("/api/reports/store-trends?days=0")
    assert resp.status_code == 422


# ── /api/reports/product-trends/{product_id} ─────────────────────────────────

def test_product_trends_empty(tmp_path):
    _setup_api_db(tmp_path, "ptrend.db")
    client = TestClient(app)
    resp = client.get("/api/reports/product-trends/prod-xyz")
    assert resp.status_code == 200
    assert resp.json() == []


# ── /api/reports/summary ──────────────────────────────────────────────────────

def test_summary_endpoint_returns_dict(tmp_path):
    _setup_api_db(tmp_path, "summary.db")
    client = TestClient(app)
    resp = client.get("/api/reports/summary")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


# ── /api/reports/top-improvers ────────────────────────────────────────────────

def test_top_improvers_empty(tmp_path):
    _setup_api_db(tmp_path, "top.db")
    client = TestClient(app)
    resp = client.get("/api/reports/top-improvers")
    assert resp.status_code == 200
    assert resp.json() == []


def test_top_improvers_limit_validation(tmp_path):
    _setup_api_db(tmp_path, "top2.db")
    client = TestClient(app)
    # limit=0 should fail validation (ge=1)
    resp = client.get("/api/reports/top-improvers?limit=0")
    assert resp.status_code == 422


# ── /api/reports/snapshot-dates ──────────────────────────────────────────────

def test_snapshot_dates_empty(tmp_path):
    _setup_api_db(tmp_path, "snapdates.db")
    client = TestClient(app)
    resp = client.get("/api/reports/snapshot-dates")
    assert resp.status_code == 200
    assert resp.json() == []


# ── /api/reports/snapshot/{date} ─────────────────────────────────────────────

def test_snapshot_detail_nonexistent_date(tmp_path):
    _setup_api_db(tmp_path, "snapdet.db")
    client = TestClient(app)
    resp = client.get("/api/reports/snapshot/2099-01-01")
    assert resp.status_code == 200
    assert resp.json() == []


# ── /api/reports/take-snapshot ───────────────────────────────────────────────

def test_take_snapshot_no_products(tmp_path):
    _setup_api_db(tmp_path, "snap.db")
    client = TestClient(app)
    resp = client.post("/api/reports/take-snapshot")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Snapshot tamamlandi"


# ── /api/reports/score-change-log ─────────────────────────────────────────────

def test_score_change_log_empty(tmp_path):
    _setup_api_db(tmp_path, "sclog.db")
    client = TestClient(app)
    resp = client.get("/api/reports/score-change-log")
    assert resp.status_code == 200
    assert resp.json() == []


def test_score_change_log_with_filters(tmp_path):
    _setup_api_db(tmp_path, "sclog2.db")
    client = TestClient(app)
    resp = client.get(
        "/api/reports/score-change-log?start_date=2025-01-01&end_date=2025-12-31&limit=10"
    )
    assert resp.status_code == 200


def test_score_change_log_limit_too_large_returns_422(tmp_path):
    _setup_api_db(tmp_path, "sclog3.db")
    client = TestClient(app)
    resp = client.get("/api/reports/score-change-log?limit=9999")
    assert resp.status_code == 422


# ── /api/reports/hourly-activity ─────────────────────────────────────────────

def test_hourly_activity_empty(tmp_path):
    _setup_api_db(tmp_path, "hourly.db")
    client = TestClient(app)
    resp = client.get("/api/reports/hourly-activity")
    assert resp.status_code == 200
    assert resp.json() == []


# ── /api/reports/daily-activity ──────────────────────────────────────────────

def test_daily_activity_empty(tmp_path):
    _setup_api_db(tmp_path, "daily.db")
    client = TestClient(app)
    resp = client.get("/api/reports/daily-activity")
    assert resp.status_code == 200
    assert resp.json() == []


# ── /api/reports/score-distribution ─────────────────────────────────────────

def test_score_distribution_empty(tmp_path):
    _setup_api_db(tmp_path, "dist.db")
    client = TestClient(app)
    resp = client.get("/api/reports/score-distribution")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── /api/reports/operation-metrics ───────────────────────────────────────────

def test_operation_metrics_empty(tmp_path):
    _setup_api_db(tmp_path, "opmet.db")
    client = TestClient(app)
    resp = client.get("/api/reports/operation-metrics")
    assert resp.status_code == 200


# ── /api/reports/score-change-summary ────────────────────────────────────────

def test_score_change_summary_empty(tmp_path):
    _setup_api_db(tmp_path, "scsum.db")
    client = TestClient(app)
    resp = client.get("/api/reports/score-change-summary")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)

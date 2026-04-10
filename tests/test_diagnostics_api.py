"""Tests for api/routers/diagnostics.py."""

import asyncio
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

import data.db as db_mod
from api.dependencies import get_manager
from api.main import app
from core.models import AppConfig


def _setup_api_db(tmp_path, name):
    db_mod.DB_PATH = tmp_path / name
    db_mod._pool = None
    db_mod._pool_initialized = False
    asyncio.run(db_mod.init_db())
    db_mod._pool = None
    db_mod._pool_initialized = False


class _DiagnosticsManager:
    def __init__(self, config: AppConfig | None = None):
        self._config = config or AppConfig(
            ikas_store_name="test-store",
            ikas_client_id="client-id",
            ikas_client_secret="client-secret",
            ai_provider="none",
        )
        self.chat_has_mcp = bool(self._config.ikas_mcp_token)
        self.chat_mcp_initialized = False
        self.chat_mcp_tool_count = 0
        self.chat_mcp_tools: list[dict[str, str]] = []

    def get_config(self) -> AppConfig:
        return self._config

    def get_provider_health(self) -> dict[str, str]:
        if self._config.ai_provider == "none":
            return {"status": "disabled", "message": "Provider yok"}
        return {"status": "ok", "message": "Bagli"}


def _override_manager(stub=None):
    app.dependency_overrides[get_manager] = lambda: stub or _DiagnosticsManager()


def _clear():
    app.dependency_overrides.clear()


def test_diagnostics_summary_returns_expected_blocks(tmp_path):
    _setup_api_db(tmp_path, "diagnostics.db")
    _override_manager()

    client = TestClient(app)
    try:
        response = client.get("/api/diagnostics/summary")
    finally:
        _clear()

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] in {"unknown", "degraded", "healthy", "down"}
    assert "providers" in body
    assert "mcp" in body
    assert "database" in body
    assert "workers" in body
    assert "prompt_cache" in body
    assert "task_runtime" in body
    assert "store_context" in body
    assert "active_jobs" in body
    assert isinstance(body["debug_report"], str)


def test_diagnostics_summary_flags_stuck_tasks(tmp_path):
    _setup_api_db(tmp_path, "diagnostics-stuck.db")
    stale_at = (datetime.now() - timedelta(minutes=10)).isoformat()
    asyncio.run(
        db_mod.create_task(
            "stuck-task",
            "batch_job",
            status="running",
            progress=12,
            payload={"feedback": {"stage": "applying", "last_event_at": stale_at, "status_message": "IKAS'a yaziliyor"}},
            result={"total_count": 10, "processed_count": 1, "failed_count": 0, "skipped_count": 0},
            started_at=stale_at,
            heartbeat_at=stale_at,
        )
    )

    async def _age_task():
        async with db_mod.connection() as conn:
            await conn.execute(
                "UPDATE tasks SET updated_at = ?, heartbeat_at = ? WHERE id = ?",
                (stale_at, stale_at, "stuck-task"),
            )
            await conn.commit()

    asyncio.run(_age_task())

    _override_manager()
    client = TestClient(app)
    try:
        response = client.get("/api/diagnostics/summary")
    finally:
        _clear()

    assert response.status_code == 200
    body = response.json()
    assert body["workers"]["stuck_count"] >= 1
    assert any(issue["reason_code"] == "worker_stuck" and issue["scope"] == "job" for issue in body["issues"])
    assert any(item["id"] == "stuck-task" and item["stuck"] for item in body["active_jobs"]["items"])


def test_diagnostics_summary_reports_mcp_token_missing(tmp_path):
    _setup_api_db(tmp_path, "diagnostics-mcp-missing.db")
    manager = _DiagnosticsManager(AppConfig(
        ikas_store_name="test-store",
        ikas_client_id="client-id",
        ikas_client_secret="client-secret",
        ai_provider="none",
        ikas_mcp_token="",
    ))
    _override_manager(manager)

    client = TestClient(app)
    try:
        response = client.get("/api/diagnostics/summary")
    finally:
        _clear()

    assert response.status_code == 200
    mcp = response.json()["mcp"]
    assert mcp["error_code"] == "mcp_token_missing"
    assert mcp["status"] == "unknown"
    assert mcp["has_token"] is False
    assert "mcp_token_missing" in mcp["reason_codes"]


def test_diagnostics_summary_reports_mcp_not_initialized(tmp_path):
    _setup_api_db(tmp_path, "diagnostics-mcp-not-init.db")
    manager = _DiagnosticsManager(AppConfig(
        ikas_store_name="test-store",
        ikas_client_id="client-id",
        ikas_client_secret="client-secret",
        ai_provider="none",
        ikas_mcp_token="mcp_token",
    ))
    manager.chat_mcp_initialized = False
    _override_manager(manager)

    client = TestClient(app)
    try:
        response = client.get("/api/diagnostics/summary")
    finally:
        _clear()

    assert response.status_code == 200
    mcp = response.json()["mcp"]
    assert mcp["error_code"] == "mcp_not_initialized"
    assert mcp["status"] == "degraded"
    assert mcp["has_token"] is True
    assert "mcp_not_initialized" in mcp["reason_codes"]


def test_diagnostics_summary_reports_empty_mcp_tool_list(tmp_path):
    _setup_api_db(tmp_path, "diagnostics-mcp-empty-tools.db")
    manager = _DiagnosticsManager(AppConfig(
        ikas_store_name="test-store",
        ikas_client_id="client-id",
        ikas_client_secret="client-secret",
        ai_provider="none",
        ikas_mcp_token="mcp_token",
    ))
    manager.chat_mcp_initialized = True
    manager.chat_mcp_tool_count = 0
    manager.chat_mcp_tools = []
    _override_manager(manager)

    client = TestClient(app)
    try:
        response = client.get("/api/diagnostics/summary")
    finally:
        _clear()

    assert response.status_code == 200
    mcp = response.json()["mcp"]
    assert mcp["error_code"] == "mcp_tool_list_empty"
    assert mcp["status"] == "degraded"
    assert mcp["initialized"] is True
    assert "mcp_tool_list_empty" in mcp["reason_codes"]


def test_diagnostics_summary_reports_mcp_ready_state(tmp_path):
    _setup_api_db(tmp_path, "diagnostics-mcp-ready.db")
    manager = _DiagnosticsManager(AppConfig(
        ikas_store_name="test-store",
        ikas_client_id="client-id",
        ikas_client_secret="client-secret",
        ai_provider="none",
        ikas_mcp_token="mcp_token",
    ))
    manager.chat_mcp_initialized = True
    manager.chat_mcp_tool_count = 2
    manager.chat_mcp_tools = [
        {"name": "listOrder", "description": "Order query"},
        {"name": "listCustomer", "description": "Customer query"},
    ]
    _override_manager(manager)

    client = TestClient(app)
    try:
        response = client.get("/api/diagnostics/summary")
    finally:
        _clear()

    assert response.status_code == 200
    mcp = response.json()["mcp"]
    assert mcp["status"] == "healthy"
    assert mcp["error_code"] is None
    assert mcp["tool_count"] == 2
    assert mcp["tool_names"] == ["listOrder", "listCustomer"]

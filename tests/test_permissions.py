import pytest

from core.models import AppConfig, SeoSuggestion
from core.permissions import (
    PermissionDecisionError,
    PermissionRequest,
    PermissionRule,
    build_runtime_allow_rule,
    create_permission_engine,
)
from core.product_manager import ProductManager


def _make_manager(audit_records: list | None = None) -> ProductManager:
    manager = object.__new__(ProductManager)
    manager._config = AppConfig()

    async def audit_logger(record):
        if audit_records is not None:
            audit_records.append(record)

    manager._permission_engine = create_permission_engine(manager._config, audit_logger=audit_logger)

    class _FakeIkas:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def update_product(self, product_id: str, updates: dict) -> bool:
            self.calls.append((product_id, dict(updates)))
            return True

    manager._ikas = _FakeIkas()
    return manager


@pytest.mark.anyio
async def test_permission_engine_resolution_order_uses_last_matching_scope():
    audit_records = []

    async def audit_logger(record):
        audit_records.append(record)

    engine = create_permission_engine(
        AppConfig(),
        audit_logger=audit_logger,
        global_rules=[PermissionRule(scope="global", behavior="ask", operation="apply")],
        project_rules=[PermissionRule(scope="project", behavior="deny", operation="apply")],
        session_rules=[PermissionRule(scope="session", behavior="ask", operation="apply")],
    )

    decision = await engine.evaluate(
        PermissionRequest(operation="apply", target="prod-1", source="test"),
        runtime_rules=[PermissionRule(scope="runtime_override", behavior="allow", operation="apply")],
    )

    assert decision.behavior == "allow"
    assert decision.matched_rule is not None
    assert decision.matched_rule.scope == "runtime_override"
    assert [entry["scope"] for entry in decision.resolution_trace] == [
        "global",
        "project",
        "session",
        "runtime_override",
    ]
    assert len(audit_records) == 1


@pytest.mark.anyio
async def test_permission_engine_audits_approval_required_decision():
    audit_records = []

    async def audit_logger(record):
        audit_records.append(record)

    engine = create_permission_engine(AppConfig(), audit_logger=audit_logger)

    decision = await engine.evaluate(
        PermissionRequest(operation="rollback", target="prod-1", source="test"),
    )

    assert decision.behavior == "ask"
    assert len(audit_records) == 1
    assert audit_records[0].operation == "rollback"
    assert audit_records[0].decision == "ask"


@pytest.mark.anyio
async def test_product_manager_clear_local_data_requires_explicit_approval(monkeypatch):
    from data import db as db_module

    manager = _make_manager()
    called = False

    async def fake_clear_all_data():
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(db_module, "clear_all_data", fake_clear_all_data)

    with pytest.raises(PermissionDecisionError) as exc_info:
        await manager.clear_local_data()

    assert exc_info.value.decision.behavior == "ask"
    assert called is False


@pytest.mark.anyio
async def test_product_manager_clear_local_data_allows_runtime_override(monkeypatch):
    from data import db as db_module

    manager = _make_manager()
    called = False

    async def fake_clear_all_data():
        nonlocal called
        called = True
        return {
            "products": 1,
            "seo_scores": 2,
            "suggestions": 3,
            "operation_log": 4,
        }

    monkeypatch.setattr(db_module, "clear_all_data", fake_clear_all_data)

    result = await manager.clear_local_data(
        permission_rules=[build_runtime_allow_rule("db_reset", description="Test override")],
    )

    assert called is True
    assert result["products"] == 1


@pytest.mark.anyio
async def test_product_manager_apply_suggestions_requires_explicit_approval():
    manager = _make_manager()
    suggestion = SeoSuggestion(
        product_id="prod-1",
        original_name="Urun",
        suggested_name="Yeni Urun",
        original_description="Aciklama",
        status="approved",
    )

    with pytest.raises(PermissionDecisionError) as exc_info:
        await manager.apply_suggestions([suggestion])

    assert exc_info.value.decision.behavior == "ask"
    assert manager._ikas.calls == []


@pytest.mark.anyio
async def test_product_manager_apply_batch_job_requires_explicit_approval(monkeypatch):
    from data import db as db_module

    manager = _make_manager()
    called = False

    async def fake_get_batch_items(job_id: str):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(db_module, "get_batch_items", fake_get_batch_items)

    with pytest.raises(PermissionDecisionError) as exc_info:
        await manager.apply_batch_job("job-1", {"target_fields": []})

    assert exc_info.value.decision.behavior == "ask"
    assert called is False


@pytest.mark.anyio
async def test_product_manager_rollback_requires_explicit_approval():
    manager = _make_manager()

    with pytest.raises(PermissionDecisionError) as exc_info:
        await manager.rollback_product("prod-1", {"name": "Eski"})

    assert exc_info.value.decision.behavior == "ask"
    assert manager._ikas.calls == []

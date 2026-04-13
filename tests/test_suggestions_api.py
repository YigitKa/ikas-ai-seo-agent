"""API tests for the suggestions router (api/routers/suggestions.py)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from api.dependencies import get_manager
from api.main import app
from core.models import Product, SeoScore, SeoSuggestion
from data import db


def _build_product(product_id: str = "p1") -> Product:
    return Product(
        id=product_id,
        name=f"Product {product_id}",
        description="<p>Turkce</p>",
        description_translations={"tr": "<p>Turkce</p>"},
    )


def _build_score(product_id: str = "p1", total_score: int = 65) -> SeoScore:
    return SeoScore(
        product_id=product_id,
        total_score=total_score,
        title_score=8,
        description_score=12,
        english_description_score=1,
        meta_score=8,
        meta_desc_score=6,
        keyword_score=6,
        content_quality_score=7,
        technical_seo_score=8,
        readability_score=3,
    )


def _build_suggestion(product_id: str = "p1") -> SeoSuggestion:
    return SeoSuggestion(
        product_id=product_id,
        original_name=f"Product {product_id}",
        suggested_name=f"SEO Product {product_id}",
        original_description="<p>eski</p>",
        suggested_description="<p>yeni</p>",
        suggested_meta_title="SEO Product - Brand",
        suggested_meta_description="Rewritten meta description with CTA.",
        thinking_text="thinking log",
    )


class _StubManager:
    def __init__(self) -> None:
        self.approved_calls = 0
        self.rejected_calls: list[str] = []
        self.approved_ids: list[str] = []
        self.update_calls: list[SeoSuggestion] = []
        self._approved: list[SeoSuggestion] = []
        self._latest: SeoSuggestion | None = None
        self.apply_count = 0
        self.rewrite_called_with: dict[str, Any] = {}
        self.field_rewrite_called_with: dict[str, Any] = {}
        self.translate_called = False
        self.analyze_fallback_calls: list[str] = []

    def get_token_usage(self):
        return {"input": 10, "output": 5, "estimated_cost": 0.001}

    async def analyze_product(self, product: Product) -> SeoScore:
        self.analyze_fallback_calls.append(product.id)
        return _build_score(product.id)

    async def rewrite_product(self, product: Product, score: SeoScore, skill_slug: str = ""):
        self.rewrite_called_with = {"pid": product.id, "skill": skill_slug}
        return _build_suggestion(product.id)

    def rewrite_field(self, field: str, product: Product, score: SeoScore, skill_slug: str = ""):
        self.field_rewrite_called_with = {"field": field, "pid": product.id, "skill": skill_slug}
        return f"new-{field}", "thinking"

    def translate_description_to_en(self, product: Product, skill_slug: str = ""):
        self.translate_called = True
        return "English translation", "thinking"

    def validate_skill_for_flow(self, skill_slug: str, flow: str) -> None:
        if skill_slug == "bad-skill":
            raise ValueError("Invalid skill for flow")

    async def approve_suggestion(self, product_id: str) -> None:
        self.approved_ids.append(product_id)

    async def reject_suggestion(self, product_id: str) -> None:
        self.rejected_calls.append(product_id)

    async def get_latest_suggestion(self, product_id: str):
        return self._latest

    async def save_or_update_pending_suggestion(self, suggestion: SeoSuggestion) -> None:
        self.update_calls.append(suggestion)

    async def get_approved_suggestions(self):
        return list(self._approved)

    async def apply_suggestions(self, approved, permission_rules=None) -> int:
        self.apply_count = len(approved)
        return len(approved)


def _client(manager: _StubManager) -> TestClient:
    app.dependency_overrides[get_manager] = lambda: manager
    return TestClient(app)


def _clear() -> None:
    app.dependency_overrides.clear()


# ── POST /api/suggestions/generate/{id} ─────────────────────────────────────

def test_generate_suggestion_uses_existing_score(monkeypatch):
    product = _build_product("p1")

    async def _fake_get_product(pid):
        return product

    async def _fake_latest_score(pid):
        return _build_score(pid)

    monkeypatch.setattr(db, "get_product", _fake_get_product)
    monkeypatch.setattr(db, "get_latest_score", _fake_latest_score)

    manager = _StubManager()
    client = _client(manager)
    try:
        response = client.post("/api/suggestions/generate/p1?skill_slug=my-skill")
    finally:
        _clear()

    assert response.status_code == 200
    body = response.json()
    assert body["suggestion"]["product_id"] == "p1"
    assert body["thinking_text"] == "thinking log"
    assert body["token_usage"]["input_tokens"] == 10
    assert body["token_usage"]["output_tokens"] == 5
    assert manager.rewrite_called_with == {"pid": "p1", "skill": "my-skill"}
    # No fallback analyze since score existed.
    assert manager.analyze_fallback_calls == []


def test_generate_suggestion_falls_back_to_analyze_when_no_score(monkeypatch):
    async def _fake_get_product(pid):
        return _build_product(pid)

    async def _fake_latest_score(pid):
        return None

    monkeypatch.setattr(db, "get_product", _fake_get_product)
    monkeypatch.setattr(db, "get_latest_score", _fake_latest_score)

    manager = _StubManager()
    client = _client(manager)
    try:
        response = client.post("/api/suggestions/generate/p1")
    finally:
        _clear()

    assert response.status_code == 200
    assert manager.analyze_fallback_calls == ["p1"]


def test_generate_suggestion_returns_404_when_product_missing(monkeypatch):
    async def _fake_get_product(pid):
        return None

    monkeypatch.setattr(db, "get_product", _fake_get_product)

    client = _client(_StubManager())
    try:
        response = client.post("/api/suggestions/generate/missing")
    finally:
        _clear()

    assert response.status_code == 404


def test_generate_suggestion_returns_400_on_rewrite_value_error(monkeypatch):
    async def _fake_get_product(pid):
        return _build_product(pid)

    async def _fake_latest_score(pid):
        return _build_score(pid)

    monkeypatch.setattr(db, "get_product", _fake_get_product)
    monkeypatch.setattr(db, "get_latest_score", _fake_latest_score)

    class _FailingManager(_StubManager):
        async def rewrite_product(self, product, score, skill_slug=""):
            raise ValueError("No AI provider configured")

    client = _client(_FailingManager())
    try:
        response = client.post("/api/suggestions/generate/p1")
    finally:
        _clear()

    assert response.status_code == 400
    assert "No AI provider" in response.json()["detail"]


# ── POST /api/suggestions/generate-field/{id} ───────────────────────────────

def test_generate_field_rewrite_for_regular_field(monkeypatch):
    async def _fake_get_product(pid):
        return _build_product(pid)

    async def _fake_latest_score(pid):
        return _build_score(pid)

    monkeypatch.setattr(db, "get_product", _fake_get_product)
    monkeypatch.setattr(db, "get_latest_score", _fake_latest_score)

    manager = _StubManager()
    client = _client(manager)
    try:
        response = client.post(
            "/api/suggestions/generate-field/p1",
            json={"product_id": "p1", "field": "meta_title", "skill_slug": ""},
        )
    finally:
        _clear()

    assert response.status_code == 200
    assert response.json()["field_value"] == "new-meta_title"
    assert manager.field_rewrite_called_with["field"] == "meta_title"
    assert manager.translate_called is False


def test_generate_field_rewrite_desc_en_uses_translation(monkeypatch):
    async def _fake_get_product(pid):
        return _build_product(pid)

    async def _fake_latest_score(pid):
        return _build_score(pid)

    monkeypatch.setattr(db, "get_product", _fake_get_product)
    monkeypatch.setattr(db, "get_latest_score", _fake_latest_score)

    manager = _StubManager()
    client = _client(manager)
    try:
        response = client.post(
            "/api/suggestions/generate-field/p1",
            json={"product_id": "p1", "field": "desc_en"},
        )
    finally:
        _clear()

    assert response.status_code == 200
    assert response.json()["field_value"] == "English translation"
    assert manager.translate_called is True


def test_generate_field_rewrite_returns_404_when_product_missing(monkeypatch):
    async def _fake_get_product(pid):
        return None

    monkeypatch.setattr(db, "get_product", _fake_get_product)

    client = _client(_StubManager())
    try:
        response = client.post(
            "/api/suggestions/generate-field/x",
            json={"product_id": "x", "field": "meta_title"},
        )
    finally:
        _clear()

    assert response.status_code == 404


# ── GET /api/suggestions/{id} ───────────────────────────────────────────────

def test_get_suggestions_returns_list(monkeypatch):
    async def _fake_by_product(pid):
        return [_build_suggestion(pid)]

    monkeypatch.setattr(db, "get_suggestions_by_product", _fake_by_product)

    client = TestClient(app)
    response = client.get("/api/suggestions/p1")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["product_id"] == "p1"


# ── PATCH /api/suggestions/{id}/approve and /reject ─────────────────────────

def test_approve_suggestion_invokes_manager():
    manager = _StubManager()
    client = _client(manager)
    try:
        response = client.patch("/api/suggestions/p1/approve")
    finally:
        _clear()

    assert response.status_code == 200
    assert manager.approved_ids == ["p1"]
    assert "p1" in response.json()["message"]


def test_reject_suggestion_invokes_manager():
    manager = _StubManager()
    client = _client(manager)
    try:
        response = client.patch("/api/suggestions/p1/reject")
    finally:
        _clear()

    assert response.status_code == 200
    assert manager.rejected_calls == ["p1"]


# ── PATCH /api/suggestions/{id}/update ──────────────────────────────────────

def test_update_suggestion_fields_returns_404_when_no_pending():
    manager = _StubManager()
    manager._latest = None
    client = _client(manager)
    try:
        response = client.patch(
            "/api/suggestions/p1/update",
            json={
                "product_id": "p1",
                "fields": [{"field": "name", "value": "X"}],
            },
        )
    finally:
        _clear()

    assert response.status_code == 404


def test_update_suggestion_fields_applies_each_field():
    manager = _StubManager()
    manager._latest = _build_suggestion("p1")
    client = _client(manager)
    try:
        response = client.patch(
            "/api/suggestions/p1/update",
            json={
                "product_id": "p1",
                "fields": [
                    {"field": "name", "value": "New Name"},
                    {"field": "meta_title", "value": "New Meta"},
                ],
            },
        )
    finally:
        _clear()

    assert response.status_code == 200
    assert len(manager.update_calls) == 1
    saved = manager.update_calls[0]
    assert saved.suggested_name == "New Name"
    assert saved.suggested_meta_title == "New Meta"


# ── POST /api/suggestions/apply ─────────────────────────────────────────────

def test_apply_approved_returns_zero_when_empty():
    manager = _StubManager()
    manager._approved = []
    client = _client(manager)
    try:
        response = client.post("/api/suggestions/apply")
    finally:
        _clear()

    assert response.status_code == 200
    assert response.json() == {"applied": 0, "total": 0}
    assert manager.apply_count == 0


def test_apply_approved_applies_all_pending():
    manager = _StubManager()
    manager._approved = [_build_suggestion("a"), _build_suggestion("b")]
    client = _client(manager)
    try:
        response = client.post("/api/suggestions/apply")
    finally:
        _clear()

    assert response.status_code == 200
    assert response.json() == {"applied": 2, "total": 2}
    assert manager.apply_count == 2

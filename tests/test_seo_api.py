"""API tests for the SEO router (api/routers/seo.py)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_manager
from api.main import app
from core.models import Product, SeoScore
from data import db


def _build_product(product_id: str = "p1", category: str | None = "Giyim") -> Product:
    return Product(
        id=product_id,
        name=f"Product {product_id}",
        description="<p>Turkce aciklama</p>",
        description_translations={"tr": "<p>Turkce aciklama</p>"},
        category=category,
        price=199.90,
    )


def _build_score(product_id: str = "p1", total_score: int = 72) -> SeoScore:
    return SeoScore(
        product_id=product_id,
        total_score=total_score,
        title_score=10,
        description_score=15,
        english_description_score=2,
        meta_score=10,
        meta_desc_score=8,
        keyword_score=8,
        content_quality_score=8,
        technical_seo_score=9,
        readability_score=4,
    )


class _StubManager:
    def __init__(self, *, products: list[Product] | None = None) -> None:
        self._products = products or []
        self.analyze_calls: list[str] = []
        self.score_calls = 0

    async def get_cached_products(self) -> list[Product]:
        return list(self._products)

    async def score_products(self, products: list[Product]):
        self.score_calls += 1
        return [(p, _build_score(p.id)) for p in products]

    async def analyze_product(self, product: Product) -> SeoScore:
        self.analyze_calls.append(product.id)
        return _build_score(product.id, total_score=65)


def _override_manager(manager: _StubManager) -> TestClient:
    app.dependency_overrides[get_manager] = lambda: manager
    return TestClient(app)


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


# ── /api/seo/analyze ────────────────────────────────────────────────────────

def test_analyze_all_returns_count_when_products_cached():
    manager = _StubManager(products=[_build_product("a"), _build_product("b")])
    client = _override_manager(manager)
    try:
        response = client.post("/api/seo/analyze")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["message"] == "Analyzed 2 products"
    assert manager.score_calls == 1


def test_analyze_all_returns_400_when_no_products_cached():
    manager = _StubManager(products=[])
    client = _override_manager(manager)
    try:
        response = client.post("/api/seo/analyze")
    finally:
        _clear_overrides()

    assert response.status_code == 400
    assert "No products cached" in response.json()["detail"]


# ── /api/seo/analyze/{product_id} ───────────────────────────────────────────

def test_analyze_one_returns_score_for_existing_product(monkeypatch):
    product = _build_product("p42")

    async def _fake_get_product(pid: str):
        return product if pid == "p42" else None

    monkeypatch.setattr(db, "get_product", _fake_get_product)

    manager = _StubManager()
    client = _override_manager(manager)
    try:
        response = client.post("/api/seo/analyze/p42")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == "p42"
    assert body["score"]["product_id"] == "p42"
    assert manager.analyze_calls == ["p42"]


def test_analyze_one_returns_404_when_product_missing(monkeypatch):
    async def _fake_get_product(pid: str):
        return None

    monkeypatch.setattr(db, "get_product", _fake_get_product)

    client = _override_manager(_StubManager())
    try:
        response = client.post("/api/seo/analyze/missing-id")
    finally:
        _clear_overrides()

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


# ── /api/seo/scores/{product_id} ────────────────────────────────────────────

def test_get_score_returns_latest_score(monkeypatch):
    async def _fake_latest(pid: str):
        return _build_score(pid, total_score=88)

    monkeypatch.setattr(db, "get_latest_score", _fake_latest)

    client = TestClient(app)
    response = client.get("/api/seo/scores/p99")

    assert response.status_code == 200
    assert response.json()["score"]["total_score"] == 88


def test_get_score_returns_404_when_missing(monkeypatch):
    async def _fake_latest(pid: str):
        return None

    monkeypatch.setattr(db, "get_latest_score", _fake_latest)

    client = TestClient(app)
    response = client.get("/api/seo/scores/none")

    assert response.status_code == 404
    assert response.json()["detail"] == "No score found"


# ── /api/seo/generate-llms-txt ──────────────────────────────────────────────

def test_generate_llms_txt_includes_summaries_grouped_by_category(monkeypatch):
    product_a = _build_product("a", category="Giyim")
    product_b = _build_product("b", category="Aksesuar")
    product_c = _build_product("c", category="Giyim")  # has no summary

    class _FakeSummary:
        def __init__(self, text: str) -> None:
            self.summary = text

    async def _fake_all():
        return [product_a, product_b, product_c]

    async def _fake_summaries():
        return {
            "a": _FakeSummary("Product A encyclopedic summary."),
            "b": _FakeSummary("Product B encyclopedic summary."),
        }

    monkeypatch.setattr(db, "get_all_products", _fake_all)
    monkeypatch.setattr(db, "get_llms_latest_summaries_map", _fake_summaries)

    client = TestClient(app)
    response = client.get("/api/seo/generate-llms-txt")

    assert response.status_code == 200
    text = response.text
    assert text.startswith("#")
    assert "### Giyim" in text
    assert "### Aksesuar" in text
    assert "Product A encyclopedic summary." in text
    assert "Product B encyclopedic summary." in text
    # Product with no summary should be omitted.
    assert "Product c" not in text
    # Counts should reflect processed vs total.
    assert "2/3" in text


def test_generate_llms_txt_when_no_summaries_shows_empty_notice(monkeypatch):
    async def _fake_all():
        return []

    async def _fake_summaries():
        return {}

    monkeypatch.setattr(db, "get_all_products", _fake_all)
    monkeypatch.setattr(db, "get_llms_latest_summaries_map", _fake_summaries)

    client = TestClient(app)
    response = client.get("/api/seo/generate-llms-txt")

    assert response.status_code == 200
    assert "ozetlenmis urun" in response.text.lower() or "0/0" in response.text


# ── /api/seo/geo-audit ──────────────────────────────────────────────────────

def test_geo_audit_returns_synthesized_response(monkeypatch):
    sample: dict[str, Any] = {
        "url": "https://example.com",
        "timestamp": "2026-04-13T10:00:00",
        "discovery": {"business_type": "ecommerce", "crawled_pages": []},
        "analysis": {"ai_visibility": {}, "platform_analysis": {}},
        "synthesis": {"geo_score": 61, "category_scores": {}, "weights": {}},
        "report_markdown": "# GEO Audit Report",
    }

    async def _fake_run(self, url: str, max_pages: int = 8):
        assert url == "https://example.com"
        assert max_pages == 4
        return sample

    from core.seo.geo_audit import GeoAuditor
    monkeypatch.setattr(GeoAuditor, "run_full_audit", _fake_run)

    client = TestClient(app)
    response = client.post(
        "/api/seo/geo-audit",
        json={"url": "https://example.com", "max_pages": 4},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "https://example.com"
    assert body["synthesis"]["geo_score"] == 61
    assert body["report_markdown"].startswith("# GEO Audit Report")


def test_geo_audit_returns_400_when_auditor_fails(monkeypatch):
    async def _fake_run(self, url: str, max_pages: int = 8):
        raise RuntimeError("crawl timeout")

    from core.seo.geo_audit import GeoAuditor
    monkeypatch.setattr(GeoAuditor, "run_full_audit", _fake_run)

    client = TestClient(app)
    response = client.post(
        "/api/seo/geo-audit",
        json={"url": "https://example.com", "max_pages": 2},
    )

    assert response.status_code == 400
    assert "GEO audit failed" in response.json()["detail"]
    assert "crawl timeout" in response.json()["detail"]


def test_geo_audit_rejects_out_of_range_max_pages():
    """Schema validation: max_pages must be between 1 and 30."""
    client = TestClient(app)
    too_high = client.post(
        "/api/seo/geo-audit",
        json={"url": "https://example.com", "max_pages": 100},
    )
    too_low = client.post(
        "/api/seo/geo-audit",
        json={"url": "https://example.com", "max_pages": 0},
    )
    assert too_high.status_code == 422
    assert too_low.status_code == 422

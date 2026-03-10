from fastapi.testclient import TestClient

from api.main import app
from core.geo_audit import GeoAuditor


def test_geo_audit_synthesis_uses_weighted_score():
    auditor = GeoAuditor()
    synthesis = auditor._synthesize(
        ai_visibility={"citability_score": 80, "brand_mentions": {"authority_score": 50}},
        platform_analysis={"readiness": {"chatgpt": 70, "perplexity": 80, "google_aio": 90}},
        technical_seo={"score": 60},
        content_quality={"score": 75},
        schema_markup={"score": 65},
    )

    expected = int(
        80 * 0.25
        + 50 * 0.20
        + 75 * 0.20
        + 60 * 0.15
        + 65 * 0.10
        + 80 * 0.10
    )
    assert synthesis["geo_score"] == expected


def test_geo_audit_endpoint_returns_report(monkeypatch):
    async def _fake_run(self, site_url: str, max_pages: int = 8):
        return {
            "url": site_url,
            "timestamp": "2026-01-01T00:00:00Z",
            "discovery": {"business_type": "ecommerce", "pages": []},
            "analysis": {
                "ai_visibility": {},
                "platform_analysis": {},
                "technical_seo": {},
                "content_quality": {},
                "schema_markup": {},
            },
            "synthesis": {"geo_score": 72, "weights": {}, "category_scores": {}},
            "report_markdown": "# GEO Audit Report",
        }

    monkeypatch.setattr(GeoAuditor, "run_full_audit", _fake_run)

    client = TestClient(app)
    response = client.post("/api/seo/geo-audit", json={"url": "example.com", "max_pages": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == "example.com"
    assert body["synthesis"]["geo_score"] == 72
    assert body["report_markdown"].startswith("# GEO Audit Report")

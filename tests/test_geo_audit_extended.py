"""Extended tests for core/seo/geo_audit.py — individual analysis stages."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.seo.geo_audit import GeoAuditor, CrawledPage, WEIGHTS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_page_dict(url: str = "https://example.com", html: str = "") -> dict:
    """Create a page dict as produced by GeoAuditor._discover()."""
    text = CrawledPage(url=url, html=html).text
    return {"url": url, "html": html, "text": text}


def _make_discovery(pages=None, sitemap_count=0, business_type="ecommerce", url="https://example.com"):
    page_dicts = pages or [_make_page_dict(url=url)]
    return {
        "homepage_url": url,
        "business_type": business_type,
        "sitemap_url": url.rstrip("/") + "/sitemap.xml",
        "sitemap_count": sitemap_count,
        "crawled_pages": [p["url"] for p in page_dicts],
        "pages": page_dicts,
    }


# ── Synthesis weights ─────────────────────────────────────────────────────────

def test_weights_sum_to_one():
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


def test_synthesis_all_zero():
    auditor = GeoAuditor()
    synthesis = auditor._synthesize(
        ai_visibility={"citability_score": 0, "brand_mentions": {"authority_score": 0}},
        platform_analysis={"readiness": {"chatgpt": 0, "perplexity": 0, "google_aio": 0}},
        technical_seo={"score": 0},
        content_quality={"score": 0},
        schema_markup={"score": 0},
    )
    assert synthesis["geo_score"] == 0


def test_synthesis_all_hundred():
    auditor = GeoAuditor()
    synthesis = auditor._synthesize(
        ai_visibility={"citability_score": 100, "brand_mentions": {"authority_score": 100}},
        platform_analysis={"readiness": {"chatgpt": 100, "perplexity": 100, "google_aio": 100}},
        technical_seo={"score": 100},
        content_quality={"score": 100},
        schema_markup={"score": 100},
    )
    assert synthesis["geo_score"] == 100


def test_synthesis_weighted_calculation():
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


def test_synthesis_category_scores_present():
    auditor = GeoAuditor()
    synthesis = auditor._synthesize(
        ai_visibility={"citability_score": 50, "brand_mentions": {"authority_score": 60}},
        platform_analysis={"readiness": {"chatgpt": 70, "perplexity": 80, "google_aio": 90}},
        technical_seo={"score": 55},
        content_quality={"score": 65},
        schema_markup={"score": 30},
    )
    assert "category_scores" in synthesis
    assert "weights" in synthesis
    cats = synthesis["category_scores"]
    assert "ai_citability_visibility" in cats
    assert "technical_foundations" in cats


# ── _analyze_ai_visibility ────────────────────────────────────────────────────

def test_analyze_ai_visibility_empty_pages(monkeypatch):
    auditor = GeoAuditor()

    async def _fake_fetch(url):
        raise Exception("not found")

    monkeypatch.setattr(auditor, "_fetch", _fake_fetch)

    discovery = _make_discovery(pages=[_make_page_dict(html="<html><body>Short.</body></html>")])
    result = asyncio.run(auditor._analyze_ai_visibility(discovery))
    assert "citability_score" in result
    assert isinstance(result["citability_score"], (int, float))
    assert "llms_txt" in result
    assert result["llms_txt"]["present"] is False


def test_analyze_ai_visibility_with_llms_txt(monkeypatch):
    auditor = GeoAuditor()

    async def _fake_fetch(url):
        if "llms.txt" in url:
            return "# llms.txt\n- Product: Example Store"
        return ""  # robots.txt

    monkeypatch.setattr(auditor, "_fetch", _fake_fetch)

    long_html = "<html><body>" + (" ".join(["word"] * 160)) + "</body></html>"
    discovery = _make_discovery(pages=[_make_page_dict(html=long_html)])
    result = asyncio.run(auditor._analyze_ai_visibility(discovery))
    assert result["llms_txt"]["present"] is True


def test_analyze_ai_visibility_without_llms_txt(monkeypatch):
    auditor = GeoAuditor()

    async def _fake_fetch(url):
        raise Exception("404")

    monkeypatch.setattr(auditor, "_fetch", _fake_fetch)

    discovery = _make_discovery()
    result = asyncio.run(auditor._analyze_ai_visibility(discovery))
    assert result["llms_txt"]["present"] is False


# ── _analyze_technical_seo ─────────────────────────────────────────────────────

def test_analyze_technical_seo_https():
    auditor = GeoAuditor()
    html = '<html><head><meta name="viewport" content="width=device-width"><h1>Title</h1></head><body><p>Content.</p></body></html>'
    discovery = _make_discovery(
        pages=[_make_page_dict(url="https://example.com", html=html)],
        url="https://example.com",
    )
    result = asyncio.run(auditor._analyze_technical_seo(discovery))
    assert "score" in result
    assert isinstance(result["score"], (int, float))
    assert result["score"] >= 0


def test_analyze_technical_seo_http_penalized():
    auditor = GeoAuditor()
    html = "<html><body>test</body></html>"
    discovery_http = _make_discovery(pages=[_make_page_dict(url="http://example.com", html=html)], url="http://example.com")
    discovery_https = _make_discovery(pages=[_make_page_dict(url="https://example.com", html=html)], url="https://example.com")

    result_http = asyncio.run(auditor._analyze_technical_seo(discovery_http))
    result_https = asyncio.run(auditor._analyze_technical_seo(discovery_https))

    assert result_https["score"] >= result_http["score"]


# ── _analyze_content_quality ──────────────────────────────────────────────────

def test_analyze_content_quality_empty_page():
    auditor = GeoAuditor()
    discovery = _make_discovery(pages=[_make_page_dict(html="<html><body></body></html>")])
    result = asyncio.run(auditor._analyze_content_quality(discovery))
    assert "score" in result
    assert "readability" in result
    assert "eeat_signals" in result


def test_analyze_content_quality_with_eeat_signals():
    auditor = GeoAuditor()
    html = """<html><body>
    <p>Author: John Doe</p>
    <a href="/about">About Us</a>
    <a href="/contact">Contact</a>
    <div class="review">Customer review</div>
    <p>Published: 2025-01-15</p>
    """ + " ".join(["word"] * 200) + """
    </body></html>"""
    discovery = _make_discovery(pages=[_make_page_dict(html=html)])
    result = asyncio.run(auditor._analyze_content_quality(discovery))
    assert result["eeat_signals"] > 0


# ── _analyze_schema ────────────────────────────────────────────────────────────

def test_analyze_schema_no_schema():
    auditor = GeoAuditor()
    discovery = _make_discovery(pages=[_make_page_dict(html="<html><body>No schema here</body></html>")])
    result = asyncio.run(auditor._analyze_schema(discovery))
    assert result["detected"] == 0
    assert result["types"] == []
    # No schema blocks → base score is penalized (30+0+40)/3 ≈ 23
    assert result["score"] < 50


def test_analyze_schema_with_json_ld():
    auditor = GeoAuditor()
    html = """<html><head>
    <script type="application/ld+json">
    {"@type": "Product", "name": "Test Product", "@context": "https://schema.org"}
    </script>
    </head><body>Content</body></html>"""
    discovery = _make_discovery(pages=[_make_page_dict(html=html)])
    result = asyncio.run(auditor._analyze_schema(discovery))
    assert result["detected"] >= 1
    assert "Product" in result["types"]
    assert result["score"] > 0


def test_analyze_schema_multiple_types():
    auditor = GeoAuditor()
    html = """<html><head>
    <script type="application/ld+json">{"@type": "Product", "@context": "https://schema.org"}</script>
    <script type="application/ld+json">{"@type": "BreadcrumbList", "@context": "https://schema.org"}</script>
    </head><body>Content</body></html>"""
    discovery = _make_discovery(pages=[_make_page_dict(html=html)])
    result = asyncio.run(auditor._analyze_schema(discovery))
    assert result["detected"] == 2
    assert "Product" in result["types"]
    assert "BreadcrumbList" in result["types"]


# ── _analyze_platforms ────────────────────────────────────────────────────────

def test_analyze_platforms_empty():
    auditor = GeoAuditor()
    discovery = _make_discovery(pages=[_make_page_dict(html="<html><body>Simple page</body></html>")])
    result = asyncio.run(auditor._analyze_platforms(discovery))
    assert "readiness" in result
    assert "chatgpt" in result["readiness"]
    assert "perplexity" in result["readiness"]
    assert "google_aio" in result["readiness"]


def test_analyze_platforms_with_faq_signals():
    auditor = GeoAuditor()
    html = """<html><body>
    <h2>FAQ</h2>
    <p>Q: What is this product?</p>
    <p>A: It is a great product.</p>
    <p>Source: example.com</p>
    <p>Compare with competitor vs alternative</p>
    </body></html>"""
    discovery = _make_discovery(pages=[_make_page_dict(html=html)])
    result = asyncio.run(auditor._analyze_platforms(discovery))
    assert result["readiness"]["perplexity"] >= 0


# ── _normalize_url ────────────────────────────────────────────────────────────

def test_normalize_url_adds_https():
    auditor = GeoAuditor()
    assert auditor._normalize_url("example.com") == "https://example.com"


def test_normalize_url_preserves_https():
    auditor = GeoAuditor()
    assert auditor._normalize_url("https://example.com") == "https://example.com"


def test_normalize_url_empty_raises():
    auditor = GeoAuditor()
    with pytest.raises(ValueError):
        auditor._normalize_url("")


# ── _build_report ─────────────────────────────────────────────────────────────

def test_build_report_contains_score():
    auditor = GeoAuditor()
    discovery = _make_discovery()
    synthesis = {
        "geo_score": 55,
        "category_scores": {
            "ai_citability_visibility": 40,
            "brand_authority_signals": 50,
            "content_quality_eeat": 60,
            "technical_foundations": 70,
            "structured_data": 30,
            "platform_optimization": 50,
        },
        "weights": WEIGHTS,
    }
    ai_visibility = {
        "citability_score": 40,
        "llms_txt": {"present": False},
        "ai_crawler_analysis": {},
        "brand_mentions": {"authority_score": 50},
    }
    platform_analysis = {
        "readiness": {"chatgpt": 50, "perplexity": 50, "google_aio": 50},
        "recommendations": [],
    }
    technical_seo = {"score": 70, "issues": []}
    content_quality = {"score": 60, "readability": 18.0, "eeat_signals": 2, "freshness_signal": False}
    schema_markup = {"score": 30, "detected": 0, "types": [], "recommendation": "Add schema"}

    report = auditor._build_report(
        "https://example.com",
        discovery,
        ai_visibility=ai_visibility,
        platform_analysis=platform_analysis,
        technical_seo=technical_seo,
        content_quality=content_quality,
        schema_markup=schema_markup,
        synthesis=synthesis,
    )
    assert isinstance(report, str)
    assert "55" in report
    assert len(report) > 100

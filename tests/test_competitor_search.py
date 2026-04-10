"""Tests for core/clients/competitor_search.py — Google scraping-based competitor price research."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from core.clients.competitor_search import (
    CompetitorSearchClient,
    _build_query,
    _extract_domain,
    _extract_price_from_text,
    _normalize_price,
)
from core.models import CompetitorPrice, CompetitorPriceReport, Product


# ── Price normalisation ──────────────────────────────────────────────────


class TestNormalizePrice:
    def test_turkish_format(self):
        assert _normalize_price("1.234,56") == 1234.56

    def test_simple_comma_decimal(self):
        assert _normalize_price("999,99") == 999.99

    def test_dot_decimal(self):
        assert _normalize_price("999.99") == 999.99

    def test_large_turkish_format(self):
        assert _normalize_price("12.345,67") == 12345.67

    def test_empty_string(self):
        assert _normalize_price("") is None

    def test_zero(self):
        assert _normalize_price("0,00") is None

    def test_none(self):
        assert _normalize_price("") is None

    def test_no_decimals(self):
        assert _normalize_price("1000") == 1000.0


class TestExtractPriceFromText:
    def test_tl_suffix(self):
        assert _extract_price_from_text("1.234,56 TL") == 1234.56

    def test_lira_sign_prefix(self):
        assert _extract_price_from_text("₺999,99") == 999.99

    def test_try_prefix(self):
        assert _extract_price_from_text("TRY 45,00") == 45.0

    def test_tl_suffix_no_space(self):
        assert _extract_price_from_text("299,90TL") == 299.90

    def test_no_price(self):
        assert _extract_price_from_text("Bu urun stoklarda yok") is None

    def test_mixed_text_with_price(self):
        result = _extract_price_from_text("BioBizz Bio-Bloom 500ml - 549,90 TL")
        assert result == 549.90

    def test_dot_decimal_fallback(self):
        assert _extract_price_from_text("Price: 29.99") == 29.99


# ── Domain extraction ────────────────────────────────────────────────────


class TestExtractDomain:
    def test_simple_url(self):
        assert _extract_domain("https://www.trendyol.com/product/123") == "trendyol.com"

    def test_without_www(self):
        assert _extract_domain("https://fidanburada.com/urun") == "fidanburada.com"

    def test_subdomain(self):
        assert _extract_domain("https://shop.example.com/item") == "shop.example.com"

    def test_invalid_url(self):
        assert _extract_domain("not-a-url") == ""


# ── Query building ───────────────────────────────────────────────────────


class TestBuildQuery:
    def test_simple_name(self):
        assert _build_query("BioBizz Bio-Bloom 500 ml") == "BioBizz Bio-Bloom 500 ml"

    def test_html_stripped(self):
        result = _build_query("<b>BioBizz</b> Bio-Bloom <em>500 ml</em>")
        assert "<b>" not in result
        assert "<em>" not in result
        assert "BioBizz" in result

    def test_long_name_truncated(self):
        long_name = "A " * 100  # 200 chars
        result = _build_query(long_name)
        assert len(result) <= 80

    def test_whitespace_normalised(self):
        assert _build_query("  BioBizz   Bio-Bloom  ") == "BioBizz Bio-Bloom"


# ── Shopping results parser ──────────────────────────────────────────────


SAMPLE_SHOPPING_HTML = """
<html>
<body>
<div data-sh-gr="true">
  <h3>BioBizz Bio-Bloom 500ml Organik Gübre</h3>
  <a href="https://www.trendyol.com/biobizz/bio-bloom-500ml-p-12345">link</a>
  <span class="a8Pemb">549,90 TL</span>
  <span class="aULzUe">trendyol.com</span>
</div>
<div data-sh-gr="true">
  <h3>BioBizz Bio Bloom 500 ml</h3>
  <a href="https://fidanburada.com/biobizz-bio-bloom-500ml">link</a>
  <span class="a8Pemb">479,00 TL</span>
  <span class="aULzUe">fidanburada.com</span>
</div>
<div data-sh-gr="true">
  <h3>BioBizz Bio-Bloom 500ml</h3>
  <a href="https://www.hepsiburada.com/biobizz-bio-bloom-pm-HB123">link</a>
  <span class="a8Pemb">599,00 TL</span>
  <span class="aULzUe">hepsiburada.com</span>
</div>
</body>
</html>
"""

SAMPLE_ORGANIC_HTML = """
<html>
<body>
<div class="g">
  <a href="https://www.tohumdunyasi.com/biobizz-bio-bloom-500ml">
    <h3>BioBizz Bio-Bloom 500ml - Tohum Dünyası</h3>
  </a>
  <span>Organik sıvı gübre. Fiyat: 489,90 TL. Hemen sipariş verin.</span>
</div>
<div class="g">
  <a href="https://www.google.com/something">
    <h3>Google related</h3>
  </a>
  <span>Some Google text</span>
</div>
<div class="g">
  <a href="https://www.n11.com/urun/biobizz-bio-bloom">
    <h3>BioBizz Bio-Bloom 500ml - n11.com</h3>
  </a>
  <span>Sıvı gübre 529,00 TL Kargo bedava.</span>
</div>
</body>
</html>
"""

EMPTY_HTML = "<html><body><div>No results found</div></body></html>"


class TestParseShoppingResults:
    def test_extracts_products(self):
        client = CompetitorSearchClient()
        results = client._parse_shopping_results(SAMPLE_SHOPPING_HTML)
        assert len(results) == 3
        # Cheapest first after sorting by price
        names = [r.site_name for r in results]
        assert "fidanburada.com" in names
        assert "trendyol.com" in names

    def test_extracts_prices(self):
        client = CompetitorSearchClient()
        results = client._parse_shopping_results(SAMPLE_SHOPPING_HTML)
        prices = {r.site_name: r.price for r in results}
        assert prices["trendyol.com"] == 549.90
        assert prices["fidanburada.com"] == 479.0

    def test_empty_html(self):
        client = CompetitorSearchClient()
        results = client._parse_shopping_results(EMPTY_HTML)
        assert results == []


class TestParseOrganicResults:
    def test_extracts_prices_from_snippets(self):
        client = CompetitorSearchClient()
        results = client._parse_organic_results(SAMPLE_ORGANIC_HTML)
        assert len(results) >= 1
        # Should find tohumdunyasi.com and n11.com, skip google.com
        domains = [r.site_name for r in results]
        assert "google.com" not in domains

    def test_empty_html(self):
        client = CompetitorSearchClient()
        results = client._parse_organic_results(EMPTY_HTML)
        assert results == []


# ── Search competitors (with mocked HTTP) ────────────────────────────────


class TestSearchCompetitors:
    @pytest.mark.anyio
    async def test_shopping_results_returned(self):
        client = CompetitorSearchClient()
        with patch.object(
            client, "_fetch_google", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = SAMPLE_SHOPPING_HTML
            results = await client.search_competitors("biobizz bio bloom 500ml")

        assert len(results) > 0
        assert all(isinstance(r, CompetitorPrice) for r in results)
        # Results should be sorted by price
        prices = [r.price for r in results]
        assert prices == sorted(prices)

    @pytest.mark.anyio
    async def test_fallback_to_organic(self):
        client = CompetitorSearchClient()
        call_count = 0

        async def mock_fetch(query, search_type="shop"):
            nonlocal call_count
            call_count += 1
            if search_type == "shop":
                return EMPTY_HTML  # No shopping results
            return SAMPLE_ORGANIC_HTML

        with patch.object(client, "_fetch_google", side_effect=mock_fetch):
            results = await client.search_competitors("biobizz bio bloom")

        assert call_count == 2  # Shopping + organic
        assert len(results) > 0

    @pytest.mark.anyio
    async def test_shopping_exception_falls_back(self):
        client = CompetitorSearchClient()

        async def mock_fetch(query, search_type="shop"):
            if search_type == "shop":
                raise Exception("Timeout")
            return SAMPLE_ORGANIC_HTML

        with patch.object(client, "_fetch_google", side_effect=mock_fetch):
            results = await client.search_competitors("biobizz bio bloom")

        assert len(results) > 0

    @pytest.mark.anyio
    async def test_deduplicates_by_domain(self):
        # Two results from same domain
        html = """
        <html><body>
        <div data-sh-gr="true">
          <h3>Product A</h3>
          <a href="https://example.com/a">link</a>
          <span class="a8Pemb">100,00 TL</span>
          <span class="aULzUe">example.com</span>
        </div>
        <div data-sh-gr="true">
          <h3>Product B</h3>
          <a href="https://example.com/b">link</a>
          <span class="a8Pemb">200,00 TL</span>
          <span class="aULzUe">example.com</span>
        </div>
        </body></html>
        """
        client = CompetitorSearchClient()
        with patch.object(
            client, "_fetch_google", new_callable=AsyncMock, return_value=html
        ):
            results = await client.search_competitors("test product")

        # Should keep only cheapest per domain
        assert len(results) == 1
        assert results[0].price == 100.0

    @pytest.mark.anyio
    async def test_both_fail_returns_empty(self):
        client = CompetitorSearchClient()
        with patch.object(
            client, "_fetch_google", side_effect=Exception("Network error")
        ):
            results = await client.search_competitors("test")
        assert results == []


# ── Report building ──────────────────────────────────────────────────────


def _make_product(**kwargs) -> Product:
    defaults = {
        "id": "p1",
        "name": "BioBizz Bio-Bloom 500 ml",
        "price": 550.0,
    }
    defaults.update(kwargs)
    return Product(**defaults)


class TestBuildReport:
    def test_basic_report(self):
        client = CompetitorSearchClient()
        product = _make_product(price=550.0)
        competitors = [
            CompetitorPrice(site_name="a.com", product_name="P", price=400.0, url="https://a.com/p"),
            CompetitorPrice(site_name="b.com", product_name="P", price=500.0, url="https://b.com/p"),
            CompetitorPrice(site_name="c.com", product_name="P", price=600.0, url="https://c.com/p"),
        ]
        report = client.build_report(product, competitors, "test query")

        assert report.product_id == "p1"
        assert report.lowest_price == 400.0
        assert report.highest_price == 600.0
        assert report.average_price == 500.0
        assert report.competitor_count == 3
        assert report.our_price == 550.0

    def test_cheapest_position(self):
        client = CompetitorSearchClient()
        product = _make_product(price=100.0)
        competitors = [
            CompetitorPrice(site_name="a.com", product_name="P", price=200.0, url="https://a.com/p"),
            CompetitorPrice(site_name="b.com", product_name="P", price=300.0, url="https://b.com/p"),
        ]
        report = client.build_report(product, competitors, "q")
        assert report.price_position == "en_ucuz"

    def test_above_average_position(self):
        client = CompetitorSearchClient()
        product = _make_product(price=600.0)
        competitors = [
            CompetitorPrice(site_name="a.com", product_name="P", price=400.0, url="https://a.com/p"),
            CompetitorPrice(site_name="b.com", product_name="P", price=500.0, url="https://b.com/p"),
        ]
        report = client.build_report(product, competitors, "q")
        # avg=450, our=600 → 33% above → "ortalama_ustu" or "en_pahali"
        assert report.price_position in ("ortalama_ustu", "en_pahali")
        assert report.price_difference_pct is not None
        assert report.price_difference_pct > 0

    def test_no_competitors(self):
        client = CompetitorSearchClient()
        product = _make_product(price=550.0)
        report = client.build_report(product, [], "q")
        assert report.competitor_count == 0
        assert report.lowest_price is None
        assert "bulunamadi" in report.recommendation.lower()

    def test_no_our_price(self):
        client = CompetitorSearchClient()
        product = _make_product(price=None)
        competitors = [
            CompetitorPrice(site_name="a.com", product_name="P", price=400.0, url="https://a.com/p"),
        ]
        report = client.build_report(product, competitors, "q")
        assert report.price_position == ""
        assert "tanimlanmamis" in report.recommendation.lower()

    def test_below_average_position(self):
        client = CompetitorSearchClient()
        product = _make_product(price=380.0)
        competitors = [
            CompetitorPrice(site_name="a.com", product_name="P", price=350.0, url="https://a.com/p"),
            CompetitorPrice(site_name="b.com", product_name="P", price=500.0, url="https://b.com/p"),
            CompetitorPrice(site_name="c.com", product_name="P", price=600.0, url="https://c.com/p"),
        ]
        report = client.build_report(product, competitors, "q")
        # avg=483.33, our=380 → ~-21% → "ortalama_alti" (not cheapest since 350 < 380)
        assert report.price_position == "ortalama_alti"

    def test_average_position(self):
        client = CompetitorSearchClient()
        product = _make_product(price=500.0)
        competitors = [
            CompetitorPrice(site_name="a.com", product_name="P", price=480.0, url="https://a.com/p"),
            CompetitorPrice(site_name="b.com", product_name="P", price=520.0, url="https://b.com/p"),
        ]
        report = client.build_report(product, competitors, "q")
        assert report.price_position == "ortalama"

"""Google search-based competitor price research client.

Scrapes Google Shopping and organic search results to find competitor prices
for a given product. Extracts prices from both large marketplaces (Trendyol,
Hepsiburada) and independent e-commerce sites.
"""

from __future__ import annotations

import asyncio
import logging
import re
import statistics
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from core.models import CompetitorPrice, CompetitorPriceReport, Product

logger = logging.getLogger(__name__)

# ── Price extraction patterns (Turkish formats) ────────────────────────────

# Matches: 1.234,56 TL | ₺999,99 | TRY 45,00 | 999,99 TL
_PRICE_WITH_CURRENCY = re.compile(
    r"(?:₺|TL|TRY)\s*(\d{1,3}(?:\.\d{3})*,\d{2})"
    r"|(\d{1,3}(?:\.\d{3})*,\d{2})\s*(?:₺|TL|TRY)"
)
# Fallback: plain Turkish decimal e.g. 1.234,56 or 999,99
_PRICE_TR_DECIMAL = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")
# Fallback: plain dot-decimal e.g. 999.99
_PRICE_DOT_DECIMAL = re.compile(r"(\d+\.\d{2})\b")

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
]


def _normalize_price(text: str) -> float | None:
    """Convert a Turkish-formatted price string to float.

    Examples:
        '1.234,56' → 1234.56
        '999,99'   → 999.99
        '999.99'   → 999.99
        '₺1.234,56 TL' → 1234.56
    """
    if not text:
        return None
    text = text.strip()
    # Try Turkish format first: dots=thousands, comma=decimal
    if "," in text:
        cleaned = text.replace(".", "").replace(",", ".")
    else:
        cleaned = text
    # Remove any remaining non-numeric chars (except dot)
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    if not cleaned:
        return None
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def _extract_price_from_text(text: str) -> float | None:
    """Extract the first price from a text string."""
    # Try currency-prefixed/suffixed first
    m = _PRICE_WITH_CURRENCY.search(text)
    if m:
        raw = m.group(1) or m.group(2)
        return _normalize_price(raw)
    # Try plain Turkish decimal
    m = _PRICE_TR_DECIMAL.search(text)
    if m:
        return _normalize_price(m.group(1))
    # Try plain dot decimal
    m = _PRICE_DOT_DECIMAL.search(text)
    if m:
        return _normalize_price(m.group(1))
    return None


def _extract_domain(url: str) -> str:
    """Extract clean domain from a URL."""
    try:
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.")
    except Exception:
        return ""


def _build_query(product_name: str) -> str:
    """Build a clean search query from a product name."""
    from core.utils.html import html_to_plain_text

    text = html_to_plain_text(product_name)
    # Remove excessive whitespace
    text = " ".join(text.split())
    # Truncate if too long
    if len(text) > 80:
        text = text[:80].rsplit(" ", 1)[0]
    return text.strip()


class CompetitorSearchClient:
    """Scrapes Google search results to find competitor prices."""

    GOOGLE_BASE = "https://www.google.com.tr/search"

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = httpx.Timeout(timeout)
        self._headers = {
            "User-Agent": _USER_AGENTS[0],
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    # ── Public API ──────────────────────────────────────────────────────

    async def search_competitors(
        self,
        query: str,
        *,
        max_results: int = 10,
    ) -> list[CompetitorPrice]:
        """Search Google for competitor prices.

        Tries Google Shopping first, falls back to organic search.
        """
        results: list[CompetitorPrice] = []

        # 1) Google Shopping
        try:
            shopping_html = await self._fetch_google(
                query, search_type="shop"
            )
            results = self._parse_shopping_results(shopping_html)
        except Exception as exc:
            logger.warning("Google Shopping scrape failed: %s", exc)

        # 2) Fallback: organic search with "fiyat" suffix
        if not results:
            try:
                organic_html = await self._fetch_google(
                    f"{query} fiyat", search_type="organic"
                )
                results = self._parse_organic_results(organic_html)
            except Exception as exc:
                logger.warning("Google organic scrape failed: %s", exc)

        # Deduplicate by domain, keep cheapest per domain
        seen: dict[str, CompetitorPrice] = {}
        for r in results:
            domain = _extract_domain(r.url)
            if domain and (domain not in seen or r.price < seen[domain].price):
                seen[domain] = r
        unique = sorted(seen.values(), key=lambda p: p.price)
        return unique[:max_results]

    def build_report(
        self,
        product: Product,
        competitors: list[CompetitorPrice],
        query: str,
    ) -> CompetitorPriceReport:
        """Build a price comparison report with market positioning analysis."""
        report = CompetitorPriceReport(
            product_id=product.id,
            product_name=product.name,
            query_used=query,
            our_price=product.price,
            competitors=competitors,
            competitor_count=len(competitors),
            searched_at=datetime.now(),
        )

        if not competitors:
            report.recommendation = (
                "Rakip fiyat bilgisi bulunamadi. "
                "Farkli bir arama sorgusu deneyin."
            )
            return report

        prices = [c.price for c in competitors]
        report.lowest_price = min(prices)
        report.highest_price = max(prices)
        report.average_price = round(statistics.mean(prices), 2)

        if product.price is not None and product.price > 0:
            avg = report.average_price
            our = product.price
            diff_pct = round(((our - avg) / avg) * 100, 1) if avg else 0
            report.price_difference_pct = diff_pct

            if our <= report.lowest_price:
                report.price_position = "en_ucuz"
                report.recommendation = (
                    "En dusuk fiyat sizde. "
                    "Fiyat avantajinizi SEO icerikte vurgulayabilirsiniz."
                )
            elif diff_pct < -10:
                report.price_position = "ortalama_alti"
                report.recommendation = (
                    f"Piyasa ortalamasinin %{abs(diff_pct):.0f} altindasiniz. "
                    "Rekabetci bir fiyat."
                )
            elif diff_pct <= 10:
                report.price_position = "ortalama"
                report.recommendation = (
                    "Piyasa ortalamasina yakinsiniz. "
                    "Deger onermenizi guclendirin."
                )
            elif diff_pct <= 25:
                report.price_position = "ortalama_ustu"
                report.recommendation = (
                    f"Piyasa ortalamasinin %{diff_pct:.0f} uzerinde. "
                    "Premium konumlandirma veya fiyat revizyonu degerlendirin."
                )
            else:
                report.price_position = "en_pahali"
                report.recommendation = (
                    f"En yuksek fiyatlardan biri (%{diff_pct:.0f} uzerinde). "
                    "Premium degeri acikca belirtin veya fiyat guncelleyin."
                )
        else:
            report.recommendation = (
                "Urun fiyati tanimlanmamis. "
                "Fiyat karsilastirmasi icin urun fiyatini girin."
            )

        return report

    # ── Internal: HTTP fetch ────────────────────────────────────────────

    async def _fetch_google(
        self, query: str, search_type: str = "shop"
    ) -> str:
        """Fetch a Google search results page."""
        params: dict[str, str] = {
            "q": query,
            "gl": "tr",
            "hl": "tr",
        }
        if search_type == "shop":
            params["tbm"] = "shop"
            params["num"] = "20"
        else:
            params["num"] = "15"

        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            headers=self._headers,
        ) as client:
            resp = await client.get(self.GOOGLE_BASE, params=params)
            resp.raise_for_status()
            return resp.text

    # ── Internal: Google Shopping parser ─────────────────────────────────

    def _parse_shopping_results(self, html: str) -> list[CompetitorPrice]:
        """Parse Google Shopping results HTML."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[CompetitorPrice] = []

        # Google Shopping product cards are in various container classes.
        # Look for common patterns: sh-dgr__content, sh-dlr__list-result, etc.
        # Each card typically has a title, price, and merchant info.

        # Strategy 1: Look for elements with price-like data attributes
        for card in soup.select("[data-sh-gr]"):
            result = self._extract_shopping_card(card)
            if result:
                results.append(result)

        # Strategy 2: Look for shopping result containers
        if not results:
            for card in soup.select(".sh-dgr__content, .sh-dlr__list-result"):
                result = self._extract_shopping_card(card)
                if result:
                    results.append(result)

        # Strategy 3: Broader search — any element with a price and a link
        if not results:
            results = self._extract_prices_from_soup(soup)

        return results

    def _extract_shopping_card(self, card: Any) -> CompetitorPrice | None:
        """Extract price data from a single Google Shopping card element."""
        # Find price
        price_el = (
            card.select_one("[data-sh-or='price']")
            or card.select_one(".a8Pemb, .HRLxBb, .kHxwFf")
            or card.select_one("span:-soup-contains('TL')")
        )
        if not price_el:
            return None
        price_text = price_el.get_text(strip=True)
        price = _extract_price_from_text(price_text)
        if price is None:
            return None

        # Find product name
        title_el = (
            card.select_one("h3")
            or card.select_one(".tAxDx, .Xjkr3b, .EI11Pd")
            or card.select_one("a[title]")
        )
        title = ""
        if title_el:
            title = title_el.get_text(strip=True)

        # Find URL
        link_el = card.select_one("a[href]")
        url = ""
        if link_el:
            href = link_el.get("href", "")
            if href.startswith("/url?"):
                # Google redirect URL — extract actual URL
                from urllib.parse import parse_qs, urlparse as _urlparse
                parsed = _urlparse(href)
                qs = parse_qs(parsed.query)
                url = qs.get("q", qs.get("url", [""]))[0]
            elif href.startswith("http"):
                url = href

        # Find merchant/site name
        merchant_el = card.select_one(
            ".aULzUe, .IuHnof, .E5ocAb, .b5ycib"
        )
        site_name = ""
        if merchant_el:
            site_name = merchant_el.get_text(strip=True)
        if not site_name and url:
            site_name = _extract_domain(url)

        if not site_name:
            return None

        return CompetitorPrice(
            site_name=site_name,
            product_name=title or site_name,
            price=price,
            url=url,
        )

    # ── Internal: Organic search parser ─────────────────────────────────

    def _parse_organic_results(self, html: str) -> list[CompetitorPrice]:
        """Parse Google organic search results for price information."""
        soup = BeautifulSoup(html, "html.parser")
        return self._extract_prices_from_soup(soup)

    def _extract_prices_from_soup(
        self, soup: BeautifulSoup
    ) -> list[CompetitorPrice]:
        """Extract prices from any Google results page by scanning all divs."""
        results: list[CompetitorPrice] = []

        # Look for search result blocks (divs with class 'g' or data-hveid)
        for block in soup.select("div.g, div[data-hveid]"):
            # Find a link
            link_el = block.select_one("a[href^='http']")
            if not link_el:
                continue
            url = link_el.get("href", "")
            if not url.startswith("http"):
                continue

            domain = _extract_domain(url)
            # Skip Google's own domains
            if not domain or "google" in domain:
                continue

            # Get all text in this block and search for prices
            block_text = block.get_text(" ", strip=True)
            price = _extract_price_from_text(block_text)
            if price is None:
                continue

            # Get title
            title_el = block.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else domain

            results.append(
                CompetitorPrice(
                    site_name=domain,
                    product_name=title,
                    price=price,
                    url=url,
                )
            )

        return results

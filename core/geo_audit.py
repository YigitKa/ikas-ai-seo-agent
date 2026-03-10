"""GEO (Generative Engine Optimization) audit pipeline.

Implements a full audit flow:
1) Discovery (homepage + sitemap crawl)
2) Parallel analysis (5 analysis agents)
3) Synthesis (weighted GEO score)
4) Report (prioritized action plan)
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx

from core.html_utils import html_to_plain_text

AI_CRAWLERS = [
    "GPTBot",
    "ChatGPT-User",
    "CCBot",
    "ClaudeBot",
    "Claude-Web",
    "anthropic-ai",
    "PerplexityBot",
    "Google-Extended",
    "GoogleOther",
    "Bytespider",
    "Amazonbot",
    "Applebot-Extended",
    "Meta-ExternalAgent",
    "OAI-SearchBot",
]

BRAND_PLATFORMS = {
    "youtube": "youtube.com",
    "reddit": "reddit.com",
    "wikipedia": "wikipedia.org",
    "linkedin": "linkedin.com",
    "x": "x.com",
    "twitter": "twitter.com",
    "github": "github.com",
    "medium": "medium.com",
    "trustpilot": "trustpilot.com",
    "g2": "g2.com",
    "quora": "quora.com",
}

WEIGHTS = {
    "ai_citability_visibility": 0.25,
    "brand_authority_signals": 0.20,
    "content_quality_eeat": 0.20,
    "technical_foundations": 0.15,
    "structured_data": 0.10,
    "platform_optimization": 0.10,
}


@dataclass
class CrawledPage:
    url: str
    html: str

    @property
    def text(self) -> str:
        return html_to_plain_text(self.html)


class GeoAuditor:
    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    async def run_full_audit(self, site_url: str, max_pages: int = 8) -> dict[str, Any]:
        normalized_url = self._normalize_url(site_url)
        discovery = await self._discover(normalized_url, max_pages=max_pages)

        ai_visibility, platform_analysis, technical_seo, content_quality, schema_markup = await asyncio.gather(
            self._analyze_ai_visibility(discovery),
            self._analyze_platforms(discovery),
            self._analyze_technical_seo(discovery),
            self._analyze_content_quality(discovery),
            self._analyze_schema(discovery),
        )

        synthesis = self._synthesize(
            ai_visibility=ai_visibility,
            platform_analysis=platform_analysis,
            technical_seo=technical_seo,
            content_quality=content_quality,
            schema_markup=schema_markup,
        )
        report_markdown = self._build_report(
            normalized_url,
            discovery,
            ai_visibility,
            platform_analysis,
            technical_seo,
            content_quality,
            schema_markup,
            synthesis,
        )

        return {
            "url": normalized_url,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "discovery": discovery,
            "analysis": {
                "ai_visibility": ai_visibility,
                "platform_analysis": platform_analysis,
                "technical_seo": technical_seo,
                "content_quality": content_quality,
                "schema_markup": schema_markup,
            },
            "synthesis": synthesis,
            "report_markdown": report_markdown,
        }

    def _normalize_url(self, url: str) -> str:
        candidate = url.strip()
        if not candidate:
            raise ValueError("URL bos olamaz")
        if not candidate.startswith(("http://", "https://")):
            candidate = f"https://{candidate}"
        return candidate

    async def _fetch(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def _discover(self, site_url: str, max_pages: int = 8) -> dict[str, Any]:
        homepage_html = await self._fetch(site_url)
        homepage = CrawledPage(url=site_url, html=homepage_html)

        sitemap_url = urljoin(site_url.rstrip("/") + "/", "sitemap.xml")
        sitemap_entries: list[str] = []
        try:
            sitemap_xml = await self._fetch(sitemap_url)
            sitemap_entries = self._extract_sitemap_urls(sitemap_xml)[:max_pages]
        except Exception:
            sitemap_entries = []

        crawl_targets = [u for u in sitemap_entries if self._same_domain(site_url, u)]
        pages = await self._crawl_pages(crawl_targets)
        all_pages = [homepage] + pages

        business_type = self._detect_business_type(homepage.text)
        return {
            "homepage_url": site_url,
            "business_type": business_type,
            "sitemap_url": sitemap_url,
            "sitemap_count": len(sitemap_entries),
            "crawled_pages": [p.url for p in all_pages],
            "pages": [{"url": p.url, "html": p.html, "text": p.text} for p in all_pages],
        }

    def _extract_sitemap_urls(self, xml_text: str) -> list[str]:
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return []
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        locs = [node.text.strip() for node in root.findall(f".//{ns}loc") if node.text]
        if locs:
            return locs
        return [node.text.strip() for node in root.findall(".//loc") if node.text]

    async def _crawl_pages(self, urls: list[str]) -> list[CrawledPage]:
        if not urls:
            return []

        async def _one(target: str) -> CrawledPage | None:
            try:
                html = await self._fetch(target)
                return CrawledPage(url=target, html=html)
            except Exception:
                return None

        result = await asyncio.gather(*[_one(u) for u in urls])
        return [p for p in result if p is not None]

    def _same_domain(self, base_url: str, candidate_url: str) -> bool:
        return urlparse(base_url).netloc == urlparse(candidate_url).netloc

    def _detect_business_type(self, text: str) -> str:
        lower = text.lower()
        if any(k in lower for k in ["add to cart", "sepete ekle", "product", "urun"]):
            return "ecommerce"
        if any(k in lower for k in ["pricing", "free trial", "enterprise", "demo"]):
            return "saas"
        if any(k in lower for k in ["reservation", "book", "appointment"]):
            return "service"
        return "content"

    async def _analyze_ai_visibility(self, discovery: dict[str, Any]) -> dict[str, Any]:
        pages = discovery["pages"]
        passages = self._collect_passages([p["text"] for p in pages])
        citability_score, citability_notes = self._score_citability(passages)

        robots_url = urljoin(discovery["homepage_url"].rstrip("/") + "/", "robots.txt")
        robots_text = ""
        try:
            robots_text = await self._fetch(robots_url)
        except Exception:
            robots_text = ""

        crawler_report = self._analyze_ai_crawlers(robots_text)

        llms_url = urljoin(discovery["homepage_url"].rstrip("/") + "/", "llms.txt")
        llms_present = False
        try:
            llms_present = bool((await self._fetch(llms_url)).strip())
        except Exception:
            llms_present = False

        brand_scan = self._scan_brand_mentions([p["html"] for p in pages])

        return {
            "citability_score": citability_score,
            "citability_notes": citability_notes,
            "ai_crawler_analysis": crawler_report,
            "llms_txt": {
                "present": llms_present,
                "url": llms_url,
                "recommendation": "Mevcut llms.txt dosyasini guncel tutun." if llms_present else "llms.txt olusturun ve ana kategori URL'lerini ekleyin.",
            },
            "brand_mentions": brand_scan,
        }

    async def _analyze_platforms(self, discovery: dict[str, Any]) -> dict[str, Any]:
        all_text = "\n".join([p["text"] for p in discovery["pages"]]).lower()
        faq_signal = int("faq" in all_text or "sik sorulan" in all_text)
        question_answer_signal = int("?" in all_text and any(k in all_text for k in ["nedir", "what is", "how to"]))
        source_signal = int(any(k in all_text for k in ["kaynak", "source", "reference"]))
        comparison_signal = int(any(k in all_text for k in ["vs", "karşılaştır", "comparison"]))

        def _score(*signals: int) -> int:
            return min(100, int(sum(signals) / max(len(signals), 1) * 100))

        chatgpt = _score(faq_signal, question_answer_signal, source_signal)
        perplexity = _score(source_signal, question_answer_signal, comparison_signal)
        google_aio = _score(faq_signal, comparison_signal, source_signal)

        recommendations = []
        if chatgpt < 70:
            recommendations.append("ChatGPT icin FAQ + net cevap bloklari ekleyin.")
        if perplexity < 70:
            recommendations.append("Perplexity icin kaynak/atif baglantilarini guclendirin.")
        if google_aio < 70:
            recommendations.append("Google AIO icin karsilastirma tablolari ve schema coverage artirin.")

        return {
            "readiness": {
                "chatgpt": chatgpt,
                "perplexity": perplexity,
                "google_aio": google_aio,
            },
            "recommendations": recommendations,
        }

    async def _analyze_technical_seo(self, discovery: dict[str, Any]) -> dict[str, Any]:
        homepage_html = discovery["pages"][0]["html"].lower()
        url = discovery["homepage_url"]
        https_score = 100 if url.startswith("https://") else 30
        mobile_score = 100 if 'name="viewport"' in homepage_html else 40
        security_score = 100 if "content-security-policy" in homepage_html else 50
        perf_score = 75 if "defer" in homepage_html or "preload" in homepage_html else 55
        ssr_score = 85 if "<h1" in homepage_html and "</p>" in homepage_html else 50
        score = int((https_score + mobile_score + security_score + perf_score + ssr_score) / 5)

        issues = []
        if mobile_score < 60:
            issues.append("Mobil viewport etiketi eksik.")
        if security_score < 60:
            issues.append("CSP header/etiket izine rastlanmadi.")
        if perf_score < 60:
            issues.append("Render-blocking asset optimizasyonu zayif gorunuyor.")

        return {"score": score, "issues": issues}

    async def _analyze_content_quality(self, discovery: dict[str, Any]) -> dict[str, Any]:
        texts = [p["text"] for p in discovery["pages"]]
        merged = "\n".join(texts)
        sentences = [s.strip() for s in re.split(r"[.!?]", merged) if s.strip()]
        words = re.findall(r"\w+", merged)
        avg_sentence_len = (len(words) / len(sentences)) if sentences else 0

        eeat_signals = sum(
            int(k in merged.lower())
            for k in ["author", "yazar", "about", "hakkımızda", "contact", "iletisim", "review", "inceleme"]
        )
        freshness_signal = int(bool(re.search(r"20\d{2}", merged)))

        readability_score = 100 if 10 <= avg_sentence_len <= 22 else 60
        eeat_score = min(100, eeat_signals * 20)
        freshness_score = 100 if freshness_signal else 55
        score = int((readability_score + eeat_score + freshness_score) / 3)

        return {
            "score": score,
            "readability": round(avg_sentence_len, 1),
            "eeat_signals": eeat_signals,
            "freshness_signal": bool(freshness_signal),
        }

    async def _analyze_schema(self, discovery: dict[str, Any]) -> dict[str, Any]:
        html = "\n".join([p["html"] for p in discovery["pages"]])
        script_blocks = re.findall(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html, re.I | re.S)

        schema_types: list[str] = []
        for block in script_blocks:
            schema_types.extend(re.findall(r'"@type"\s*:\s*"([^"]+)"', block))

        detection_score = 100 if script_blocks else 30
        variety_score = min(100, len(set(schema_types)) * 25)
        validation_score = 90 if script_blocks else 40
        score = int((detection_score + variety_score + validation_score) / 3)

        return {
            "score": score,
            "detected": len(script_blocks),
            "types": sorted(set(schema_types)),
            "recommendation": "Product, FAQPage ve Organization schema ekleyin." if not script_blocks else "Schema alanlarini Search Console ile dogrulayin.",
        }

    def _collect_passages(self, texts: list[str]) -> list[str]:
        passages: list[str] = []
        for text in texts:
            for paragraph in text.split("\n"):
                cleaned = paragraph.strip()
                if cleaned:
                    passages.append(cleaned)
        return passages

    def _score_citability(self, passages: list[str]) -> tuple[int, list[str]]:
        if not passages:
            return 0, ["Icerik bulunamadi"]

        optimal_count = 0
        dense_count = 0
        for p in passages:
            wc = len(re.findall(r"\w+", p))
            if 134 <= wc <= 167:
                optimal_count += 1
            if any(ch.isdigit() for ch in p) and ":" in p:
                dense_count += 1

        total = len(passages)
        ratio_optimal = optimal_count / total
        ratio_dense = dense_count / total
        score = min(100, int((ratio_optimal * 60 + ratio_dense * 40) * 100))

        notes = [
            f"Optimal uzunlukta pasajlar: {optimal_count}/{total} (134-167 kelime)",
            f"Veri-zengin pasajlar: {dense_count}/{total}",
        ]
        if optimal_count == 0:
            notes.append("AI alintilari icin 134-167 kelimelik bagimsiz bilgi bloklari ekleyin.")
        return score, notes

    def _analyze_ai_crawlers(self, robots_text: str) -> dict[str, Any]:
        allowed: list[str] = []
        blocked: list[str] = []
        neutral: list[str] = []

        lower = robots_text.lower()
        for crawler in AI_CRAWLERS:
            marker = crawler.lower()
            if marker not in lower:
                neutral.append(crawler)
                continue
            match = re.search(rf"user-agent:\s*{re.escape(marker)}[\s\S]*?(?:user-agent:|$)", lower)
            block = match.group(0) if match else ""
            if "disallow: /" in block:
                blocked.append(crawler)
            elif "allow:" in block or "disallow:" in block:
                allowed.append(crawler)
            else:
                neutral.append(crawler)

        return {
            "allowed": allowed,
            "blocked": blocked,
            "unknown": neutral,
            "recommendations": [
                "AI crawler politikalarini robots.txt icinde acikca belirtin.",
                "Kritik dokumantasyon sayfalarini AI botlarina allow edin.",
            ],
        }

    def _scan_brand_mentions(self, html_pages: list[str]) -> dict[str, Any]:
        merged = "\n".join(html_pages).lower()
        hits: dict[str, int] = {}
        for name, domain in BRAND_PLATFORMS.items():
            count = merged.count(domain)
            if count > 0:
                hits[name] = count

        coverage = min(100, len(hits) * 10)
        return {
            "platform_hits": hits,
            "platform_count": len(hits),
            "authority_score": coverage,
            "recommendation": "YouTube, Reddit, LinkedIn, Wikipedia gibi platformlarda markayi dogal sekilde gecirin.",
        }

    def _synthesize(
        self,
        *,
        ai_visibility: dict[str, Any],
        platform_analysis: dict[str, Any],
        technical_seo: dict[str, Any],
        content_quality: dict[str, Any],
        schema_markup: dict[str, Any],
    ) -> dict[str, Any]:
        ai_score = ai_visibility["citability_score"]
        brand_score = ai_visibility["brand_mentions"]["authority_score"]
        content_score = content_quality["score"]
        technical_score = technical_seo["score"]
        structured_score = schema_markup["score"]
        platform_score = int(sum(platform_analysis["readiness"].values()) / 3)

        weighted = {
            "ai_citability_visibility": ai_score,
            "brand_authority_signals": brand_score,
            "content_quality_eeat": content_score,
            "technical_foundations": technical_score,
            "structured_data": structured_score,
            "platform_optimization": platform_score,
        }
        geo_score = int(sum(weighted[key] * WEIGHTS[key] for key in WEIGHTS))

        return {
            "weights": WEIGHTS,
            "category_scores": weighted,
            "geo_score": max(0, min(100, geo_score)),
        }

    def _build_report(
        self,
        url: str,
        discovery: dict[str, Any],
        ai_visibility: dict[str, Any],
        platform_analysis: dict[str, Any],
        technical_seo: dict[str, Any],
        content_quality: dict[str, Any],
        schema_markup: dict[str, Any],
        synthesis: dict[str, Any],
    ) -> str:
        quick_wins = [
            "llms.txt dosyasi yayinlayin" if not ai_visibility["llms_txt"]["present"] else "llms.txt iceriğini guncel tutun",
            "FAQ + soru-cevap bloklari ekleyin",
            "Product/FAQPage/Organization schema coverage artirin",
        ]
        lines = [
            f"# GEO Audit Report — {url}",
            "",
            "## Discovery",
            f"- Business type: {discovery['business_type']}",
            f"- Crawled pages: {len(discovery['pages'])}",
            f"- Sitemap URLs discovered: {discovery['sitemap_count']}",
            "",
            "## Parallel Analysis",
            f"- AI Visibility score: {ai_visibility['citability_score']}",
            f"- Platform readiness (ChatGPT/Perplexity/Google AIO): {platform_analysis['readiness']}",
            f"- Technical SEO score: {technical_seo['score']}",
            f"- Content Quality score: {content_quality['score']}",
            f"- Schema score: {schema_markup['score']}",
            "",
            "## Synthesis",
            f"- Composite GEO Score: **{synthesis['geo_score']}/100**",
            "",
            "## Prioritized Action Plan (Quick Wins)",
        ]
        for idx, win in enumerate(quick_wins, start=1):
            lines.append(f"{idx}. {win}")
        return "\n".join(lines)

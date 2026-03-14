"""Agent tool definitions and toolkit factories.

Provides the AgentTool / AgentToolkit abstractions used by
AgentOrchestrator to expose capabilities to the LLM.  Each tool
carries an OpenAI-function-style JSON Schema plus an async handler.

Toolkit factories assemble curated subsets of tools for different
use-cases (SEO rewrite, chat, batch, GEO audit).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from core.models import Product, SeoScore, SeoSuggestion

logger = logging.getLogger(__name__)

# Type alias for tool handlers
ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


# ── AgentTool & AgentToolkit ─────────────────────────────────────────────


@dataclass
class AgentTool:
    """A single tool that can be invoked by the LLM."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    handler: ToolHandler | None = None

    def to_openai_function(self) -> dict[str, Any]:
        """Serialise to the OpenAI ``tools`` format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class AgentToolkit:
    """Registry of :class:`AgentTool` instances.

    Provides serialisation helpers and centralised execution.
    """

    def __init__(self, tools: list[AgentTool] | None = None) -> None:
        self._tools: dict[str, AgentTool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_openai_functions(self) -> list[dict[str, Any]]:
        """Return the list suitable for the ``tools`` parameter of a chat-completion request."""
        return [t.to_openai_function() for t in self._tools.values()]

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool by name and return the result string."""
        tool = self._tools.get(name)
        if tool is None or tool.handler is None:
            return json.dumps({"error": f"Tool '{name}' is not available.", "available_tools": self.tool_names}, ensure_ascii=False)

        start = time.monotonic()
        try:
            result = await tool.handler(args)
        except Exception as exc:
            logger.exception("Tool '%s' raised an error", name)
            result = json.dumps({"error": str(exc)}, ensure_ascii=False)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.debug("Tool '%s' executed in %d ms", name, elapsed_ms)
        return result

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# ── Built-in tool builders ───────────────────────────────────────────────
# Each function returns an AgentTool with its handler pre-wired.


def build_seo_score_product_tool() -> AgentTool:
    """Tool: score a product using the rule-based SEO analyser."""

    async def handler(args: dict[str, Any]) -> str:
        from core.seo.analyzer import analyze_product
        from data import db

        product_id = args.get("product_id", "")
        product = await db.get_product(product_id)
        if product is None:
            return json.dumps({"error": f"Product '{product_id}' not found."}, ensure_ascii=False)

        target_keywords = args.get("target_keywords")
        score = analyze_product(product, target_keywords)
        return json.dumps(score.model_dump(), ensure_ascii=False, default=str)

    return AgentTool(
        name="seo_score_product",
        description=(
            "Bir urunu kural tabanli SEO rubrigine gore skorlar. "
            "Issues ve suggestions listesini de dondurur."
        ),
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Urun ID'si"},
                "target_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hedef anahtar kelimeler (opsiyonel)",
                },
            },
            "required": ["product_id"],
        },
        handler=handler,
    )


def build_get_product_details_tool() -> AgentTool:
    """Tool: retrieve a product from the local DB."""

    async def handler(args: dict[str, Any]) -> str:
        from data import db

        product_id = args.get("product_id", "")
        product = await db.get_product(product_id)
        if product is None:
            return json.dumps({"error": f"Product '{product_id}' not found."}, ensure_ascii=False)
        return json.dumps(product.model_dump(), ensure_ascii=False, default=str)

    return AgentTool(
        name="get_product_details",
        description="Yerel veritabanindan urun detaylarini getirir.",
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Urun ID'si"},
            },
            "required": ["product_id"],
        },
        handler=handler,
    )


def build_search_products_tool() -> AgentTool:
    """Tool: search/filter products from the local DB."""

    async def handler(args: dict[str, Any]) -> str:
        from data import db

        products = await db.get_all_products()
        max_score = args.get("max_score")
        limit = args.get("limit", 20)

        if max_score is not None:
            from core.seo.analyzer import analyze_product

            filtered = []
            for p in products:
                score = analyze_product(p)
                if score.total_score <= int(max_score):
                    filtered.append({"id": p.id, "name": p.name, "score": score.total_score})
            filtered.sort(key=lambda x: x["score"])
            return json.dumps(filtered[:limit], ensure_ascii=False)

        results = [{"id": p.id, "name": p.name} for p in products[:limit]]
        return json.dumps(results, ensure_ascii=False)

    return AgentTool(
        name="search_products",
        description=(
            "Yerel veritabanindaki urunleri listeler veya filtreler. "
            "max_score ile dusuk skorlu urunleri bulabilirsiniz."
        ),
        parameters={
            "type": "object",
            "properties": {
                "max_score": {
                    "type": "integer",
                    "description": "Bu skorun altindaki urunleri filtrele (opsiyonel)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksimum sonuc sayisi (default 20)",
                },
            },
        },
        handler=handler,
    )


def build_validate_rewrite_tool() -> AgentTool:
    """Tool: score a product with hypothetical field values (before/after comparison)."""

    async def handler(args: dict[str, Any]) -> str:
        from core.seo.analyzer import analyze_product
        from data import db

        product_id = args.get("product_id", "")
        product = await db.get_product(product_id)
        if product is None:
            return json.dumps({"error": f"Product '{product_id}' not found."}, ensure_ascii=False)

        # Score original
        original_score = analyze_product(product)

        # Create modified copy with proposed values
        updates = args.get("updates", {})
        modified_data = product.model_dump()
        for field_name, value in updates.items():
            if field_name in modified_data:
                modified_data[field_name] = value
        modified_product = Product.model_validate(modified_data)
        new_score = analyze_product(modified_product)

        return json.dumps({
            "original_score": original_score.total_score,
            "new_score": new_score.total_score,
            "improvement": new_score.total_score - original_score.total_score,
            "original_summary_scores": {
                "seo": original_score.seo_score,
                "geo": original_score.geo_score,
                "aeo": original_score.aeo_score,
            },
            "new_summary_scores": {
                "seo": new_score.seo_score,
                "geo": new_score.geo_score,
                "aeo": new_score.aeo_score,
            },
            "original_breakdown": {
                "title": original_score.title_score,
                "description": original_score.description_score,
                "meta_title": original_score.meta_score,
                "meta_description": original_score.meta_desc_score,
                "keyword": original_score.keyword_score,
                "content_quality": original_score.content_quality_score,
                "technical": original_score.technical_seo_score,
                "readability": original_score.readability_score,
                "ai_citability": original_score.ai_citability_score,
            },
            "new_breakdown": {
                "title": new_score.title_score,
                "description": new_score.description_score,
                "meta_title": new_score.meta_score,
                "meta_description": new_score.meta_desc_score,
                "keyword": new_score.keyword_score,
                "content_quality": new_score.content_quality_score,
                "technical": new_score.technical_seo_score,
                "readability": new_score.readability_score,
                "ai_citability": new_score.ai_citability_score,
            },
            "remaining_issues": new_score.issues,
        }, ensure_ascii=False)

    return AgentTool(
        name="validate_rewrite",
        description=(
            "Ürün alanlarını değiştirmeden, önerilen değişikliklerle skoru simüle eder. "
            "Önceki/sonraki skor karşılaştırması döndürür."
        ),
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Urun ID'si"},
                "updates": {
                    "type": "object",
                    "description": (
                        "Simule edilecek alan degisiklikleri. "
                        "Ornek: {\"name\": \"Yeni Baslik\", \"description\": \"<p>Yeni aciklama...</p>\"}"
                    ),
                },
            },
            "required": ["product_id", "updates"],
        },
        handler=handler,
    )


def build_save_suggestion_tool() -> AgentTool:
    """Tool: save an SEO suggestion to the database."""

    async def handler(args: dict[str, Any]) -> str:
        from data import db

        product_id = args.get("product_id", "")
        product = await db.get_product(product_id)
        if product is None:
            return json.dumps({"error": f"Product '{product_id}' not found."}, ensure_ascii=False)

        from core.utils.presentation import get_tr_description_value, get_en_description_value

        suggestion = SeoSuggestion(
            product_id=product_id,
            original_name=product.name,
            suggested_name=args.get("suggested_name", ""),
            original_description=get_tr_description_value(product.description, product.description_translations),
            suggested_description=args.get("suggested_description", ""),
            original_description_en=get_en_description_value(product.description_translations),
            suggested_description_en=args.get("suggested_description_en", ""),
            original_meta_title=product.meta_title or "",
            suggested_meta_title=args.get("suggested_meta_title", ""),
            original_meta_description=product.meta_description or "",
            suggested_meta_description=args.get("suggested_meta_description", ""),
            thinking_text=args.get("thinking_text", ""),
            status="pending",
        )
        await db.save_or_update_pending_suggestion(suggestion)

        return json.dumps({
            "success": True,
            "product_id": product_id,
            "status": "pending",
            "message": "Oneri basariyla kaydedildi.",
        }, ensure_ascii=False)

    return AgentTool(
        name="save_suggestion",
        description=(
            "Optimize edilmis SEO onerilerini veritabanina kaydeder. "
            "Status 'pending' olarak kaydedilir; kullanici onayi bekler."
        ),
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Urun ID'si"},
                "suggested_name": {"type": "string", "description": "Onerilen urun adi (opsiyonel)"},
                "suggested_description": {"type": "string", "description": "Onerilen TR aciklama (HTML)"},
                "suggested_description_en": {"type": "string", "description": "Onerilen EN aciklama (opsiyonel)"},
                "suggested_meta_title": {"type": "string", "description": "Onerilen meta title"},
                "suggested_meta_description": {"type": "string", "description": "Onerilen meta description"},
                "thinking_text": {"type": "string", "description": "Dusunce sureci aciklamasi (opsiyonel)"},
            },
            "required": ["product_id"],
        },
        handler=handler,
    )


def build_get_seo_guidelines_tool() -> AgentTool:
    """Tool: return the SEO scoring rubric rules."""

    async def handler(args: dict[str, Any]) -> str:
        return json.dumps({
            "rubric": {
                "title": {"max": 15, "ideal_length": "30-60 karakter", "tips": "Power words, keyword near front, no special chars"},
                "description_tr": {"max": 20, "ideal": "Min 150 kelime, paragraf yapisi, basliklar, listeler, bold"},
                "description_en": {"max": 5, "ideal": "Min 100 kelime, Turkce karakter olmamali"},
                "meta_title": {"max": 15, "ideal_length": "50-60 karakter", "tips": "Brand separator, farkli urun adindan"},
                "meta_description": {"max": 10, "ideal_length": "120-160 karakter", "tips": "CTA icermeli"},
                "keyword_optimization": {"max": 10, "tips": "Target keywords in description/meta"},
                "content_quality": {"max": 10, "tips": "No keyword stuffing (>5%), diverse vocabulary"},
                "technical_seo": {"max": 10, "tips": "3-5 images, 3-5 tags, category, slug"},
                "readability": {"max": 5, "tips": "15-25 words/sentence, transition words"},
                "ai_citability": {"max": 10, "tips": "Structured facts, clear attributes, AI-readable"},
            },
            "total_max": 100,
        }, ensure_ascii=False)

    return AgentTool(
        name="get_seo_guidelines",
        description="SEO skorlama rubriginin kurallarini ve max puanlarini dondurur.",
        parameters={"type": "object", "properties": {}},
        handler=handler,
    )


# ── Toolkit factories ────────────────────────────────────────────────────


def create_seo_rewrite_toolkit() -> AgentToolkit:
    """Toolkit for the SEO rewrite agent: score, validate, save, guidelines."""
    return AgentToolkit([
        build_seo_score_product_tool(),
        build_get_product_details_tool(),
        build_validate_rewrite_tool(),
        build_save_suggestion_tool(),
        build_get_seo_guidelines_tool(),
    ])


def create_chat_toolkit() -> AgentToolkit:
    """Toolkit for the chat agent: all local tools."""
    return AgentToolkit([
        build_seo_score_product_tool(),
        build_get_product_details_tool(),
        build_search_products_tool(),
        build_validate_rewrite_tool(),
        build_save_suggestion_tool(),
        build_get_seo_guidelines_tool(),
    ])


def create_batch_toolkit() -> AgentToolkit:
    """Toolkit for batch SEO optimisation: search, score, validate, save."""
    return AgentToolkit([
        build_search_products_tool(),
        build_seo_score_product_tool(),
        build_get_product_details_tool(),
        build_validate_rewrite_tool(),
        build_save_suggestion_tool(),
    ])

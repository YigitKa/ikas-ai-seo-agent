"""Multi-turn conversational chat service with MCP tool integration.

Allows users to chat about their products using local AI models (Ollama,
LM Studio, etc.) while the AI can autonomously call ikas MCP tools to
fetch real-time store data during the conversation.

Use cases:
  - Product Q&A: "Bu ürünün SEO skoru nasıl iyileştirilir?"
  - Store insights: "En çok satan 5 ürünü listele"
  - SEO coaching: "Başlık uzunluğu neden önemli?"
  - Bulk analysis: "Düşük skorlu ürünleri özetle"
  - Inventory: "Stokta azalan ürünler hangileri?"
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from core.models import AppConfig, ChatMessage, ChatResponse, Product, SeoScore
from core.mcp_client import IkasMCPClient, MCPError

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # Max sequential tool-call rounds per message
MAX_HISTORY_MESSAGES = 40  # Keep conversation manageable for context window

CHAT_SYSTEM_PROMPT_TR = """Sen bir ikas e-ticaret mağazası asistanısın. Mağaza sahibine ürünleri,
SEO optimizasyonu, stok durumu ve mağaza yönetimi konularında yardım ediyorsun.

Kurallar:
- Türkçe yanıt ver (kullanıcı İngilizce yazarsa İngilizce yanıt ver)
- Kısa ve öz yanıtlar ver, gereksiz uzatma
- Ürün verisi gerektiğinde sana sağlanan araçları kullan
- SEO önerilerinde somut ve uygulanabilir tavsiyeler ver
- Fiyat, stok ve sipariş bilgilerini doğru aktar
- Markdown formatında yanıt ver (başlıklar, listeler, kalın metin)

{product_context}
{score_context}"""

PRODUCT_CONTEXT_TEMPLATE = """
Şu an seçili ürün:
- Ad: {name}
- Kategori: {category}
- Fiyat: {price}
- SKU: {sku}
- Durum: {status}
- Meta Title: {meta_title}
- Meta Description: {meta_description}
- Etiketler: {tags}
- Açıklama (özet): {description_preview}"""

SCORE_CONTEXT_TEMPLATE = """
SEO Skoru: {total_score}/100
- Başlık: {title_score}/15
- Açıklama: {description_score}/20
- Meta Title: {meta_score}/15
- Meta Description: {meta_desc_score}/10
- Anahtar Kelime: {keyword_score}/10
- İçerik Kalitesi: {content_quality_score}/10
- Teknik SEO: {technical_seo_score}/10
- Okunabilirlik: {readability_score}/5
Sorunlar: {issues}"""


def _build_product_context(product: Product | None, score: SeoScore | None) -> str:
    """Build product context string for the system prompt."""
    product_ctx = ""
    score_ctx = ""

    if product:
        desc_preview = (product.description or "")[:200]
        if len(product.description or "") > 200:
            desc_preview += "..."
        product_ctx = PRODUCT_CONTEXT_TEMPLATE.format(
            name=product.name,
            category=product.category or "-",
            price=f"{product.price:.2f} TL" if product.price else "-",
            sku=product.sku or "-",
            status=product.status,
            meta_title=product.meta_title or "-",
            meta_description=product.meta_description or "-",
            tags=", ".join(product.tags) if product.tags else "-",
            description_preview=desc_preview or "-",
        )

    if score:
        score_ctx = SCORE_CONTEXT_TEMPLATE.format(
            total_score=score.total_score,
            title_score=score.title_score,
            description_score=score.description_score,
            meta_score=score.meta_score,
            meta_desc_score=score.meta_desc_score,
            keyword_score=score.keyword_score,
            content_quality_score=score.content_quality_score,
            technical_seo_score=score.technical_seo_score,
            readability_score=score.readability_score,
            issues="; ".join(score.issues[:5]) if score.issues else "Yok",
        )

    return CHAT_SYSTEM_PROMPT_TR.format(
        product_context=product_ctx,
        score_context=score_ctx,
    )


class ChatService:
    """Multi-turn chat service with optional MCP tool integration.

    Works with any OpenAI-compatible local model (Ollama, LM Studio)
    and can optionally use ikas MCP tools for real-time store data access.
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._mcp: IkasMCPClient | None = None
        self._mcp_initialized = False
        self._history: list[ChatMessage] = []
        self._product: Product | None = None
        self._score: SeoScore | None = None
        self._total_tokens = {"input": 0, "output": 0}

    @property
    def has_mcp(self) -> bool:
        return bool(self._config.ikas_mcp_token)

    @property
    def mcp_initialized(self) -> bool:
        return self._mcp_initialized

    @property
    def history(self) -> list[ChatMessage]:
        return list(self._history)

    @property
    def total_tokens(self) -> dict[str, int]:
        return dict(self._total_tokens)

    def set_product_context(self, product: Product | None, score: SeoScore | None = None) -> None:
        """Set the current product context for the conversation."""
        self._product = product
        self._score = score

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    async def initialize_mcp(self) -> tuple[bool, str]:
        """Initialize MCP connection. Returns (success, message)."""
        if not self._config.ikas_mcp_token:
            return False, "MCP token ayarlanmamis. Ayarlar'dan ikas MCP token'i girin."

        try:
            self._mcp = IkasMCPClient(self._config.ikas_mcp_token)
            await self._mcp.initialize()
            tools = await self._mcp.list_tools()
            self._mcp_initialized = True
            return True, f"MCP baglantisi basarili! {len(tools)} arac kesfedildi."
        except MCPError as exc:
            logger.error("MCP initialization failed: %s", exc)
            self._mcp_initialized = False
            return False, f"MCP hatasi: {exc}"
        except Exception as exc:
            logger.error("MCP connection failed: %s", exc)
            self._mcp_initialized = False
            return False, f"MCP baglanti hatasi: {exc}"

    async def send_message(self, user_message: str) -> ChatResponse:
        """Send a user message and get an AI response.

        If MCP is initialized, the AI model can call ikas tools during
        the conversation to fetch real-time store data.
        """
        # Add user message to history
        user_msg = ChatMessage(role="user", content=user_message)
        self._history.append(user_msg)

        # Trim history if too long
        if len(self._history) > MAX_HISTORY_MESSAGES:
            self._history = self._history[-MAX_HISTORY_MESSAGES:]

        # Build messages for the AI
        system_prompt = _build_product_context(self._product, self._score)
        messages = [{"role": "system", "content": system_prompt}]
        for msg in self._history:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.role == "tool" and msg.name:
                m["name"] = msg.name
            messages.append(m)

        # Get MCP tools for function calling
        tools = None
        if self._mcp_initialized and self._mcp:
            tools = self._mcp.get_tools_as_openai_functions()

        # Call the AI model with tool-use loop
        response_text = ""
        thinking_text = ""
        tool_results: list[dict[str, Any]] = []
        meta: dict[str, Any] = {}

        try:
            response_text, thinking_text, tool_results, meta = await self._chat_completion(
                messages, tools
            )
        except Exception as exc:
            error_msg = f"AI hatasi: {exc}"
            logger.error("Chat completion failed: %s", exc)
            return ChatResponse(
                content=error_msg,
                thinking="",
                tool_results=[],
                error=True,
                meta={},
            )

        # Add assistant response to history
        assistant_msg = ChatMessage(role="assistant", content=response_text)
        self._history.append(assistant_msg)

        return ChatResponse(
            content=response_text,
            thinking=thinking_text,
            tool_results=tool_results,
            error=False,
            meta=meta,
        )

    async def _chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> tuple[str, str, list[dict], dict]:
        """Run chat completion with automatic tool-call handling.

        Returns (response_text, thinking_text, tool_results, meta).
        """
        base_url = self._get_base_url()
        model = self._config.ai_model_name or self._get_default_model()
        all_tool_results: list[dict[str, Any]] = []

        for _round in range(MAX_TOOL_ROUNDS):
            request_body: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": self._config.ai_temperature,
                "max_tokens": self._config.ai_max_tokens,
            }

            # Only include tools if available and supported
            if tools and self._config.ai_provider in ("ollama", "lm-studio", "openai", "openrouter", "custom"):
                request_body["tools"] = tools

            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                headers: dict[str, str] = {"Content-Type": "application/json"}
                if self._config.ai_api_key:
                    headers["Authorization"] = f"Bearer {self._config.ai_api_key}"

                resp = await client.post(
                    f"{base_url}/chat/completions",
                    json=request_body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "stop")

            # Track tokens
            usage = data.get("usage", {})
            if usage:
                self._total_tokens["input"] += usage.get("prompt_tokens", 0)
                self._total_tokens["output"] += usage.get("completion_tokens", 0)

            meta = {
                "model": data.get("model", model),
                "finish_reason": finish_reason,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

            # Check for tool calls
            tool_calls = message.get("tool_calls")
            if tool_calls and self._mcp and self._mcp_initialized:
                # Add assistant message with tool calls to messages
                messages.append({
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": tool_calls,
                })

                # Execute each tool call via MCP
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}

                    try:
                        result = await self._mcp.call_tool(tool_name, args)
                        result_text = json.dumps(result, ensure_ascii=False, indent=2)
                    except Exception as exc:
                        result_text = json.dumps({"error": str(exc)}, ensure_ascii=False)

                    tool_result = {
                        "tool": tool_name,
                        "arguments": args,
                        "result": result_text[:2000],  # Limit size
                    }
                    all_tool_results.append(tool_result)

                    # Add tool result to messages for next round
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "name": tool_name,
                        "content": result_text,
                    })

                # Continue the loop to get the final response
                continue

            # No tool calls — we have the final response
            response_text = message.get("content", "")
            thinking_text = self._extract_thinking(response_text)
            if thinking_text:
                response_text = self._remove_thinking(response_text)

            return response_text, thinking_text, all_tool_results, meta

        # Max rounds reached
        return (
            message.get("content", "") if 'message' in dir() else "Maksimum araç çağrısı sayısına ulaşıldı.",
            "",
            all_tool_results,
            meta if 'meta' in dir() else {},
        )

    def _get_base_url(self) -> str:
        """Get the base URL for the AI provider."""
        if self._config.ai_base_url:
            url = self._config.ai_base_url.rstrip("/")
            if not url.endswith("/v1"):
                url += "/v1" if "/v1" not in url else ""
            return url

        provider = self._config.ai_provider
        defaults = {
            "ollama": "http://localhost:11434/v1",
            "lm-studio": "http://localhost:1234/v1",
            "openai": "https://api.openai.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
        }
        return defaults.get(provider, "http://localhost:11434/v1")

    def _get_default_model(self) -> str:
        """Get the default model for the provider."""
        defaults = {
            "ollama": "llama3.2",
            "lm-studio": "default",
            "openai": "gpt-4o-mini",
            "openrouter": "openai/gpt-4o-mini",
            "gemini": "gemini-1.5-flash",
            "anthropic": "claude-haiku-4-5-20251001",
        }
        return defaults.get(self._config.ai_provider, "llama3.2")

    @staticmethod
    def _extract_thinking(text: str) -> str:
        """Extract <think>...</think> blocks from response."""
        import re
        match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _remove_thinking(text: str) -> str:
        """Remove <think>...</think> blocks from response."""
        import re
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    async def close(self) -> None:
        """Close MCP connection."""
        if self._mcp:
            await self._mcp.close()
            self._mcp = None
            self._mcp_initialized = False

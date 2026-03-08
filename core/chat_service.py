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
import re
import threading
from datetime import datetime
from typing import Any, Optional

import httpx

from core.models import AppConfig, ChatMessage, ChatResponse, Product, SeoScore
from core.mcp_client import IkasMCPClient, MCPError

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # Max sequential tool-call rounds per message
MAX_HISTORY_MESSAGES = 40  # Keep conversation manageable for context window

CHAT_FLOW_SYSTEM_PROMPT_TR = """Sen bir ikas e-ticaret magazasi asistansin.
Bu sohbette 3 rol vardir:
- Kullanici: hedefi ve karari belirler
- ikas MCP: canli magaza verisini ve arac sonucunu saglar
- Local AI: veriyi yorumlar, SEO/pazarlama onerisi uretir ve yaniti birlestirir

Ana gorevin:
- Konusmayi secili urun etrafinda tut
- Canli veri gerektiginde araclardan yararlan
- MCP'den gelen ham veriyi tekrar etmek yerine ozetleyip anlamlandir
- Somut, uygulanabilir ve kisa yanit ver

Kurallar:
- Turkce yanit ver; kullanici Ingilizce yazarsa Ingilizce yanit ver
- Gerekli degilse MCP cagirisi yapma, ama stok/fiyat/varyant/magaza durumu gibi canli veri gereken yerde arac kullan
- Secili urunun promptta zaten bulunan statik SEO bilgileri icin yeniden arac cagirisi yapma
- SEO onerilerinde oncelik sirasi ve neden belirt
- Veri eksigi veya belirsizlik varsa acikca soyle
- Uretim tonu net, profesyonel ve kisa olsun
- Markdown kullanabilirsin
- Genis markdown tablolar yerine kisa listeler kullan; tabloyu yalnizca kullanici isterse kullan

Yaniti mumkunse su duzende kur:
1. Durum
2. Oneri
3. Sonraki adim

Yeniden yazim istenirse:
- 2 veya 3 alternatif sun
- Alternatiflerin farkini 1 kisa cumleyle belirt

{product_context}
{score_context}"""

CHAT_FLOW_PRODUCT_CONTEXT_TEMPLATE = """
Su an secili urun:
- Ad: {name}
- Kategori: {category}
- Fiyat: {price}
- SKU: {sku}
- Durum: {status}
- Meta Title: {meta_title}
- Meta Description: {meta_description}
- Etiketler: {tags}
- Aciklama (ozet): {description_preview}"""

CHAT_FLOW_SCORE_CONTEXT_TEMPLATE = """
SEO Skoru: {total_score}/100
- Baslik: {title_score}/15
- Aciklama: {description_score}/20
- Meta Title: {meta_score}/15
- Meta Description: {meta_desc_score}/10
- Anahtar Kelime: {keyword_score}/10
- Icerik Kalitesi: {content_quality_score}/10
- Teknik SEO: {technical_seo_score}/10
- Okunabilirlik: {readability_score}/5
Sorunlar: {issues}"""

IKAS_OPERATION_GUIDE_TR = """
ikas operasyon rehberi:

Query yetenekleri:
- Customer Management: listCustomer, listCustomerAttribute
- Location Management: listCountry, listState, listCity, listDistrict, listTown
- Merchant: getMerchant, getMerchantLicence
- Sales & Payments: listAbandonedCheckouts
- Product Management: listProduct, listProductAttribute, listProductBrand
- Order Management: listOrder, listOrderTag, listOrderTransactions
- Settings: getGlobalTaxSettings, listShippingSettings, listTaxSettings

Mutation yetenekleri:
- Customer Management: updateCustomer, addCustomerTimelineEntry
- App Integration: createMerchantAppPayment, saveWebhooks, deleteWebhook, getAppDemoDay
- Sales Channel: updateSalesChannel
- Order Management: createOrderWithTransactions, fulfillOrder, cancelFulfillment, cancelOrderLine, refundOrderLine, updateOrderPackageStatus, addOrderInvoice, removeOrderInvoice, downloadOrderInvoice, approvePendingOrderTransactions
- Product Management: createProduct, updateProduct, deleteProductList, addVariantToProduct, removeVariantFromProduct, saveVariantStocks, updateVariantPrices
- Campaign Management: createCampaign, updateCampaign, deleteCampaignList, addCouponsToCampaign
- Storefront Management: createStorefrontJSScript, updateStorefrontJSScript, deleteStorefrontJSScript
- Timeline Management: addCustomTimelineEntry, addOrderTimelineEntry

Davranis kurallari:
- Yanit verirken uygun oldugunda onerileri bu operasyon adlariyla operasyonel aksiyonlara cevir.
- Mumkunse once ilgili query ile mevcut durumu netlestir, sonra gerekiyorsa uygun mutation oner.
- Mutation gerektiren adimlarda kullanicidan net onay iste.
- Arac kullanmiyor olsan bile, nasil ilerlenebilecegini desteklenen operasyon adlariyla kisaca anlat.
- Yanitin sonunda konusmayi ilerletecek tek bir sonraki adim veya soru oner.
- Desteklenmeyen operasyon adi uydurma.
"""

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

IKAS_MENTION_PATTERN = re.compile(r"@\s*ikas\b", re.IGNORECASE)
LOCAL_MENTION_PATTERN = re.compile(r"@\s*local\b", re.IGNORECASE)
STOCK_HINT_PATTERN = re.compile(r"\bstok\b|\benvanter\b|\bkaç tane\b|\bkaç kald[iı]\b", re.IGNORECASE)
PRICE_HINT_PATTERN = re.compile(r"\bfiyat\b|\bücret\b|\bprice\b", re.IGNORECASE)
VARIANT_HINT_PATTERN = re.compile(r"\bvaryant\b|\bvariant\b", re.IGNORECASE)
ORDER_HINT_PATTERN = re.compile(r"\bsipari[sş]\b|\border\b", re.IGNORECASE)
CUSTOMER_HINT_PATTERN = re.compile(r"\bm[uü]steri\b|\bcustomer\b", re.IGNORECASE)
LIVE_PRODUCT_HINT_PATTERNS = (
    STOCK_HINT_PATTERN,
    PRICE_HINT_PATTERN,
    VARIANT_HINT_PATTERN,
)

SELECTED_PRODUCT_LIVE_QUERY = """query listProduct($id: StringFilterInput, $pagination: PaginationInput) {
  listProduct(id: $id, pagination: $pagination) {
    count
    data {
      id
      name
      totalStock
      metaData {
        slug
      }
      categories {
        id
        name
      }
      variants {
        id
        sku
        sellIfOutOfStock
        stocks {
          stockCount
          stockLocationId
        }
        prices {
          sellPrice
          discountPrice
          currencyCode
        }
      }
    }
  }
}"""


def _get_routing_mode(user_message: str) -> str:
    has_ikas = bool(IKAS_MENTION_PATTERN.search(user_message))
    has_local = bool(LOCAL_MENTION_PATTERN.search(user_message))
    if has_ikas and has_local:
        return "hybrid"
    if has_ikas:
        return "ikas"
    if has_local:
        return "local"
    return "local"


def _build_product_context(product: Product | None, score: SeoScore | None) -> str:
    """Build product context string for the system prompt."""
    product_ctx = ""
    score_ctx = ""

    if product:
        desc_preview = (product.description or "")[:200]
        if len(product.description or "") > 200:
            desc_preview += "..."
        product_ctx = CHAT_FLOW_PRODUCT_CONTEXT_TEMPLATE.format(
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
        score_ctx = CHAT_FLOW_SCORE_CONTEXT_TEMPLATE.format(
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

    return CHAT_FLOW_SYSTEM_PROMPT_TR.format(
        product_context=product_ctx,
        score_context=score_ctx,
    ) + "\n\n" + IKAS_OPERATION_GUIDE_TR


def _extract_message_directives(user_message: str) -> tuple[str, str | None, bool]:
    """Parse @ikas / @local mentions into routing instructions.

    Returns (cleaned_message, routing_instruction, allow_tools).
    """
    routing_mode = _get_routing_mode(user_message)

    cleaned = IKAS_MENTION_PATTERN.sub("", user_message)
    cleaned = LOCAL_MENTION_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned_message = cleaned or user_message.strip()

    if routing_mode == "hybrid":
        return (
            cleaned_message,
            (
                "Bu mesaj hem @ikas hem @local ile etiketlendi. "
                "Uygun bir ikas MCP araci kullan, sonra sonucu kisa ve net bicimde yorumla. "
                "Gerekirse ilgili query/mutation operasyonlariyla sonraki adimi oner; mutation icin onay iste."
            ),
            True,
        )

    if routing_mode == "ikas":
        return (
            cleaned_message,
            (
                "Bu mesaj @ikas ile etiketlendi. "
                "Mumkunse uygun bir ikas MCP araci kullanmadan yanit verme. "
                "Canli veri cekemiyorsan bunu acikca belirt. "
                "Yanitta ilgili operasyonlarla nasil devam edilecegini de oner; mutation gerekiyorsa onay iste."
            ),
            True,
        )

    if routing_mode == "local":
        return (
            cleaned_message,
            (
                "Bu mesaj @local ile etiketlendi veya mention icermiyor. "
                "Arac kullanma; yalnizca mevcut urun ve sohbet baglamina gore yanit ver. "
                "Ama uygun oldugunda desteklenen ikas operasyon adlariyla nasil ilerlenebilecegini oner."
            ),
            False,
        )

    return cleaned_message, None, False


def _build_tool_catalog_instruction(
    tool_summaries: list[dict[str, str]],
    user_message: str,
) -> str | None:
    if not tool_summaries:
        return None

    tool_names = [tool["name"] for tool in tool_summaries if tool.get("name")]
    instructions = [
        "MCP araci kullanacaksan yalnizca asagidaki tam tool adlarini kullan.",
        "Tool adi uydurma. Ornegin get_stock gibi bir isim yoksa kullanma.",
    ]

    if "listProduct" in tool_names and (
        STOCK_HINT_PATTERN.search(user_message)
        or PRICE_HINT_PATTERN.search(user_message)
        or VARIANT_HINT_PATTERN.search(user_message)
    ):
        instructions.append(
            "Bu mesaj stok/fiyat/varyant ile ilgili. Uygunsa once listProduct aracini kullan."
        )
        instructions.append(
            "listProduct cagirirken tam GraphQL query string'i gonder ve operationName olarak listProduct kullan."
        )

    if "listOrder" in tool_names and ORDER_HINT_PATTERN.search(user_message):
        instructions.append("Bu mesaj siparis ile ilgili. Uygunsa listOrder ile basla.")

    if "listCustomer" in tool_names and CUSTOMER_HINT_PATTERN.search(user_message):
        instructions.append("Bu mesaj musteri ile ilgili. Uygunsa listCustomer ile basla.")

    if any(name.startswith("update") or name.startswith("create") or name.startswith("delete") for name in tool_names):
        instructions.append(
            "Kullanici acikca degisiklik istemedikce mutation kullanma; once query araclari tercih et."
        )

    visible_names = ", ".join(tool_names[:40])
    instructions.append(f"Kullanilabilir toollar: {visible_names}")
    return " ".join(instructions)


def _build_local_no_think_instruction(config: AppConfig) -> str | None:
    if config.ai_provider not in ("ollama", "lm-studio"):
        return None
    if config.ai_thinking_mode:
        return None
    return (
        "Yerel model kullaniyorsun. Ic muhakemeyi, <think> bloklarini ve uzun dusunce metinlerini "
        "yazma; dogrudan nihai yaniti ver. /no_think"
    )


def _format_chat_error(exc: Exception) -> str:
    if isinstance(exc, httpx.ReadTimeout):
        return (
            "AI istegi zaman asimina ugradi. Yerel model dusunce modunda takilmis olabilir; "
            "daha kisa bir istek deneyin veya Thinking Mode'u kapatin."
        )
    if isinstance(exc, httpx.ConnectError):
        return "AI endpoint'ine baglanilamadi. Base URL ve model server durumunu kontrol edin."
    if isinstance(exc, httpx.HTTPStatusError):
        return f"AI endpoint'i HTTP {exc.response.status_code} dondu."

    text = str(exc).strip()
    return f"AI hatasi: {text}" if text else "AI istegi basarisiz oldu."


def _extract_mcp_text(result: dict[str, Any]) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return json.dumps(result, ensure_ascii=False)

    text_parts = [
        str(item.get("text", ""))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    text = "\n".join(part for part in text_parts if part).strip()
    return text or json.dumps(result, ensure_ascii=False)


def _extract_mcp_json_payload(result: dict[str, Any]) -> dict[str, Any]:
    text = _extract_mcp_text(result)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _format_decimal(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _format_money(price: dict[str, Any]) -> str:
    sell_price = price.get("sellPrice")
    discount_price = price.get("discountPrice")
    currency = str(price.get("currencyCode") or "").strip()
    sell_text = _format_decimal(sell_price)
    discount_text = _format_decimal(discount_price)
    currency_text = f" {currency}" if currency else ""
    if isinstance(discount_price, (int, float)):
        return f"{sell_text}{currency_text} (indirimli: {discount_text}{currency_text})"
    return f"{sell_text}{currency_text}"


def _first_number(*values: Any) -> int | float | None:
    for value in values:
        if isinstance(value, (int, float)):
            return value
    return None


def _build_completion_meta(data: dict[str, Any], model: str, finish_reason: str) -> dict[str, Any]:
    usage = data.get("usage", {}) if isinstance(data, dict) else {}
    stats = data.get("stats", {}) if isinstance(data, dict) else {}
    model_info = data.get("model_info", {}) if isinstance(data, dict) else {}

    input_tokens = _first_number(
        usage.get("prompt_tokens") if isinstance(usage, dict) else None,
        stats.get("input_tokens") if isinstance(stats, dict) else None,
    )
    output_tokens = _first_number(
        usage.get("completion_tokens") if isinstance(usage, dict) else None,
        stats.get("total_output_tokens") if isinstance(stats, dict) else None,
        stats.get("output_tokens") if isinstance(stats, dict) else None,
    )
    total_tokens = _first_number(
        usage.get("total_tokens") if isinstance(usage, dict) else None,
        (
            (int(input_tokens) if isinstance(input_tokens, (int, float)) else 0)
            + (int(output_tokens) if isinstance(output_tokens, (int, float)) else 0)
        ),
    )

    meta: dict[str, Any] = {
        "model": data.get("model", model),
        "finish_reason": finish_reason,
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }

    extra_fields = {
        "tokens_per_second": _first_number(
            stats.get("tokens_per_second") if isinstance(stats, dict) else None,
        ),
        "time_to_first_token_seconds": _first_number(
            stats.get("time_to_first_token_seconds") if isinstance(stats, dict) else None,
        ),
        "reasoning_output_tokens": _first_number(
            stats.get("reasoning_output_tokens") if isinstance(stats, dict) else None,
        ),
        "context_length": _first_number(
            model_info.get("context_length") if isinstance(model_info, dict) else None,
            model_info.get("max_context_length") if isinstance(model_info, dict) else None,
            stats.get("context_length") if isinstance(stats, dict) else None,
        ),
        "stop_reason": str(data.get("stop_reason") or (stats.get("stop_reason") if isinstance(stats, dict) else "") or ""),
    }

    prompt_tokens = meta["input_tokens"]
    context_length = extra_fields["context_length"]
    if isinstance(context_length, (int, float)) and context_length > 0:
        meta["context_length"] = int(context_length)
        meta["context_used_percent"] = round((prompt_tokens / context_length) * 100, 1)
        meta["context_remaining_percent"] = round(max(0.0, 100 - meta["context_used_percent"]), 1)

    for key, value in extra_fields.items():
        if key in {"context_length"}:
            continue
        if isinstance(value, (int, float)):
            meta[key] = value
        elif isinstance(value, str) and value:
            meta[key] = value

    return meta


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
        self._active_request_lock = threading.Lock()
        self._active_http_client: httpx.AsyncClient | None = None

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

    @property
    def mcp_tool_count(self) -> int:
        return self._mcp.tool_count if self._mcp else 0

    @property
    def mcp_tools(self) -> list[dict[str, str]]:
        if not self._mcp:
            return []
        return self._mcp.get_tool_summaries()

    def set_product_context(self, product: Product | None, score: SeoScore | None = None) -> None:
        """Set the current product context for the conversation."""
        self._product = product
        self._score = score

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    def cancel_active_request(self) -> bool:
        """Try to cancel the in-flight chat completion HTTP request."""
        with self._active_request_lock:
            client = self._active_http_client

        if client is None:
            return False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False

        loop.create_task(client.aclose())
        return True

    async def initialize_mcp(self) -> tuple[bool, str]:
        """Initialize MCP connection. Returns (success, message)."""
        if not self._config.ikas_mcp_token:
            return False, "MCP token ayarlanmamis. Ayarlar'dan ikas MCP token'i girin."

        try:
            self._mcp = IkasMCPClient(self._config.ikas_mcp_token)
            await self._mcp.initialize()
            await self._mcp.list_tools()
            self._mcp_initialized = True
            return True, f"MCP baglantisi basarili! {self._mcp.tool_count} operasyon hazir."
        except MCPError as exc:
            logger.error("MCP initialization failed: %s", exc)
            self._mcp_initialized = False
            return False, f"MCP hatasi: {exc}"
        except Exception as exc:
            logger.error("MCP connection failed: %s", exc)
            self._mcp_initialized = False
            return False, f"MCP baglanti hatasi: {exc}"

    async def _maybe_run_guided_mcp_request(
        self,
        user_message: str,
    ) -> tuple[str, list[dict[str, Any]], str] | None:
        """Run a deterministic MCP query for common selected-product live-data questions."""
        if not self._product or not self._mcp or not self._mcp_initialized:
            return None

        if not any(pattern.search(user_message) for pattern in LIVE_PRODUCT_HINT_PATTERNS):
            return None

        result = await self._mcp.call_tool("listProduct", {
            "query": SELECTED_PRODUCT_LIVE_QUERY,
            "variables": {
                "id": {"eq": self._product.id},
                "pagination": {"limit": 1, "page": 1},
            },
        })

        payload = _extract_mcp_json_payload(result)
        list_product = payload.get("listProduct", {}) if isinstance(payload, dict) else {}
        items = list_product.get("data", []) if isinstance(list_product, dict) else []
        product_data = items[0] if isinstance(items, list) and items else None
        if not isinstance(product_data, dict):
            return None

        total_stock = product_data.get("totalStock")
        variants = product_data.get("variants", [])
        variant_lines: list[str] = []
        fallback_variant_lines: list[str] = []
        seen_prices: list[str] = []

        if isinstance(variants, list):
            for idx, variant in enumerate(variants[:8], start=1):
                if not isinstance(variant, dict):
                    continue

                sku = str(variant.get("sku") or "-")
                stocks = variant.get("stocks", [])
                prices = variant.get("prices", [])
                stock_total = 0.0
                has_stock = False

                if isinstance(stocks, list):
                    for stock in stocks:
                        if isinstance(stock, dict) and isinstance(stock.get("stockCount"), (int, float)):
                            stock_total += float(stock["stockCount"])
                            has_stock = True

                price_summary = "-"
                if isinstance(prices, list) and prices:
                    formatted_prices = [
                        _format_money(price)
                        for price in prices
                        if isinstance(price, dict)
                    ]
                    formatted_prices = [price for price in formatted_prices if price and price != "-"]
                    if formatted_prices:
                        price_summary = ", ".join(formatted_prices[:2])
                        seen_prices.extend(formatted_prices[:2])

                stock_summary = _format_decimal(stock_total) if has_stock else "-"
                variant_lines.append(
                    f"- Varyant {idx}: sku={sku}, stok={stock_summary}, fiyat={price_summary}"
                )
                fallback_variant_lines.append(
                    f"Varyant {idx}: SKU {sku}, stok {stock_summary}, fiyat {price_summary}"
                )

        price_summary = ", ".join(dict.fromkeys(seen_prices)) if seen_prices else "-"
        stock_summary = _format_decimal(total_stock)

        context_lines = [
            "ikas MCP ile dogrulanmis secili urun canli verisi:",
            f"- Urun: {product_data.get('name') or self._product.name}",
            f"- Urun ID: {product_data.get('id') or self._product.id}",
            f"- Toplam stok: {stock_summary}",
            f"- Varyant sayisi: {len(variants) if isinstance(variants, list) else 0}",
            f"- Fiyat ozeti: {price_summary}",
        ]
        if isinstance(total_stock, (int, float)) and float(total_stock) == -1:
            context_lines.append(
                "- Not: MCP toplam stok degerini -1 dondurdu. Bu genelde stok takibinin kapali veya limitsiz satis anlamina gelebilir."
            )
        context_lines.extend(variant_lines)

        fallback_lines = [
            "**Durum**",
            f"- Urun: {product_data.get('name') or self._product.name}",
            f"- Toplam stok: {stock_summary}",
        ]
        if isinstance(total_stock, (int, float)) and float(total_stock) == -1:
            fallback_lines.append(
                "- MCP `totalStock = -1` dondurdu. Bu deger genelde stok takibinin kapali veya varyantin limitsiz satisa acik olduguna isaret eder."
            )
        if price_summary != "-":
            fallback_lines.append(f"- Fiyat ozeti: {price_summary}")
        if fallback_variant_lines:
            fallback_lines.append(f"- Varyant ozeti: {' | '.join(fallback_variant_lines[:4])}")

        fallback_lines.append("")
        fallback_lines.append("**Not**")
        fallback_lines.append("- Bu cevap dogrudan ikas MCP canli verisine dayanir.")

        return (
            "\n".join(context_lines),
            [{
                "tool": "listProduct",
                "arguments": {
                    "id": self._product.id,
                    "mode": "selected_product_live_data",
                },
                "result": _extract_mcp_text(result)[:2000],
            }],
            "\n".join(fallback_lines),
        )

    async def send_message(self, user_message: str) -> ChatResponse:
        """Send a user message and get an AI response.

        If MCP is initialized, the AI model can call ikas tools during
        the conversation to fetch real-time store data.
        """
        routing_mode = _get_routing_mode(user_message)
        cleaned_message, routing_instruction, allow_tools = _extract_message_directives(user_message)

        # Add user message to history
        user_msg = ChatMessage(role="user", content=cleaned_message)
        self._history.append(user_msg)

        # Trim history if too long
        if len(self._history) > MAX_HISTORY_MESSAGES:
            self._history = self._history[-MAX_HISTORY_MESSAGES:]

        # Build messages for the AI
        system_prompt = _build_product_context(self._product, self._score)
        messages = [{"role": "system", "content": system_prompt}]
        if routing_instruction:
            messages.append({"role": "system", "content": routing_instruction})
        local_no_think_instruction = _build_local_no_think_instruction(self._config)
        if local_no_think_instruction:
            messages.append({"role": "system", "content": local_no_think_instruction})

        guided_context = ""
        guided_tool_results: list[dict[str, Any]] = []
        guided_fallback = ""
        if allow_tools and self._mcp_initialized and self._mcp:
            try:
                guided_result = await self._maybe_run_guided_mcp_request(cleaned_message)
            except Exception as exc:
                logger.warning("Guided MCP request failed: %s", exc)
                guided_result = None

            if guided_result:
                guided_context, guided_tool_results, guided_fallback = guided_result
                if routing_mode == "ikas":
                    assistant_msg = ChatMessage(role="assistant", content=guided_fallback)
                    self._history.append(assistant_msg)
                    return ChatResponse(
                        content=guided_fallback,
                        thinking="",
                        tool_results=guided_tool_results,
                        error=False,
                        meta={
                            "model": "ikas MCP",
                            "finish_reason": "guided_mcp",
                            "source": "ikas_mcp",
                        },
                    )
                messages.append({
                    "role": "system",
                    "content": (
                        "Asagidaki ikas MCP sonucu dogrulanmis canli veridir. "
                        "Bu veriyi esas al, veri uydurma ve degistirme:\n"
                        f"{guided_context}"
                    ),
                })
        elif routing_mode == "ikas":
            messages.append({
                "role": "system",
                "content": (
                    "ikas MCP su anda hazir degil. Canli veri cekemedigini acikca belirt "
                    "ve magaza verisi uydurma."
                ),
            })

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
        if allow_tools and self._mcp_initialized and self._mcp and not guided_context:
            tools = self._mcp.get_tools_as_openai_functions()
            tool_catalog_instruction = _build_tool_catalog_instruction(self.mcp_tools, cleaned_message)
            if tool_catalog_instruction:
                messages.insert(2 if routing_instruction else 1, {
                    "role": "system",
                    "content": tool_catalog_instruction,
                })

        # Call the AI model with tool-use loop
        response_text = ""
        thinking_text = ""
        tool_results: list[dict[str, Any]] = list(guided_tool_results)
        meta: dict[str, Any] = {}

        try:
            response_text, thinking_text, completion_tool_results, meta = await self._chat_completion(
                messages, tools
            )
            tool_results.extend(completion_tool_results)
        except asyncio.CancelledError:
            logger.info("Chat request cancelled by user")
            if user_msg in self._history:
                self._history.remove(user_msg)
            raise
        except Exception as exc:
            logger.exception("Chat completion failed")
            if self._history and self._history[-1] is user_msg:
                self._history.pop()
            if guided_fallback:
                assistant_msg = ChatMessage(role="assistant", content=guided_fallback)
                self._history.append(assistant_msg)
                return ChatResponse(
                    content=guided_fallback,
                    thinking="",
                    tool_results=tool_results,
                    error=False,
                    meta={
                        "model": "ikas MCP",
                        "finish_reason": "guided_mcp_fallback",
                        "source": "ikas_mcp",
                    },
                )
            return ChatResponse(
                content=_format_chat_error(exc),
                thinking="",
                tool_results=tool_results,
                error=True,
                meta={},
            )

        if not response_text and guided_fallback:
            response_text = guided_fallback
        elif not response_text.strip() and thinking_text:
            response_text = (
                "Model nihai cevap uretmedi. Yerel model dusunce modunda takilmis olabilir; "
                "daha kisa bir istek deneyin veya Thinking Mode'u kapatin."
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

            timeout = (
                httpx.Timeout(600.0, connect=10.0)
                if self._config.ai_provider in ("ollama", "lm-studio")
                else httpx.Timeout(120.0, connect=10.0)
            )
            client = httpx.AsyncClient(timeout=timeout)
            with self._active_request_lock:
                self._active_http_client = client
            try:
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
            finally:
                with self._active_request_lock:
                    if self._active_http_client is client:
                        self._active_http_client = None
                await client.aclose()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "stop")

            # Track tokens
            meta = _build_completion_meta(data, model, finish_reason)
            self._total_tokens["input"] += int(meta.get("input_tokens", 0) or 0)
            self._total_tokens["output"] += int(meta.get("output_tokens", 0) or 0)

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
                        result_text = json.dumps({
                            "error": str(exc),
                            "available_tools": self._mcp.get_tool_names(),
                        }, ensure_ascii=False)

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
        if match:
            return match.group(1).strip()
        open_match = re.search(r"<think>(.*)$", text, re.DOTALL)
        return open_match.group(1).strip() if open_match else ""

    @staticmethod
    def _remove_thinking(text: str) -> str:
        """Remove <think>...</think> blocks from response."""
        import re
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        if "<think>" in cleaned:
            cleaned = cleaned.split("<think>", 1)[0]
        return cleaned.strip()

    async def close(self) -> None:
        """Close MCP connection."""
        self.cancel_active_request()
        if self._mcp:
            await self._mcp.close()
            self._mcp = None
            self._mcp_initialized = False

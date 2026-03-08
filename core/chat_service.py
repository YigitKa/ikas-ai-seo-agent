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
import contextlib
import json
import logging
import re
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Any, Optional

import httpx

from core.models import AppConfig, ChatMessage, ChatResponse, Product, SeoScore
from core.mcp_client import IkasMCPClient, MCPError

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # Max sequential tool-call rounds per message
MAX_HISTORY_MESSAGES = 40  # Keep conversation manageable for context window
HISTORY_SUMMARY_TRIGGER_MESSAGES = 12
HISTORY_SUMMARY_KEEP_RECENT_MESSAGES = 4
MEMORY_SUMMARIZATION_PROMPT = (
    "A\u015fa\u011f\u0131daki sohbet ge\u00e7mi\u015fini, kullan\u0131c\u0131n\u0131n "
    "niyetini, tercihlerini ve onaylanan i\u015fleri kaybetmeden tek bir "
    "k\u0131sa paragraf olarak \u00f6zetle."
)
HISTORY_SUMMARY_SYSTEM_PREFIX = "\u00d6nceki sohbetlerin \u00f6zeti: "

CHAT_FLOW_SYSTEM_PROMPT_TR = """Sen bir ikas e-ticaret magazasi SEO asistansin.
Bu sohbette 3 rol vardir:
- Kullanici: hedefi ve karari belirler
- ikas MCP: canli magaza verisini ve arac sonucunu saglar
- Local AI: secili urunun eldeki verisini yorumlar ve yaniti birlestirir

Ana gorevin:
- Konusmayi secili urun etrafinda tut
- Varsayilan olarak yalnizca mevcut SEO metrikleri, issue/suggestion alanlari ve promptta zaten bulunan urun bilgileri uzerinden tavsiye ver
- Kullanici urun aciklamasi, meta title, meta description, kategori, etiket, SKU gibi eldeki alanlari yorumlamani isterse bunu local baglamla yap
- Canli veri gerektiginde ve kullanici ozellikle isterse araclardan yararlan
- Somut, uygulanabilir ve kisa yanit ver
- Kullaniciyi urun bilgilerini duzeltmeye ve iyilestirmeye yonlendir

KRITIK DÜRÜSTLÜK KURALLARI (ASLA IHLAL ETME):
- ASLA yapmedigin bir islemi yaptigini iddia etme
- ASLA "guncelledim", "uyguladim", "degistirdim", "kaydettim" gibi ifadeler kullanma
- Sen urunleri DOGRUDAN degistiremezsin. Sen yalnizca oneri ve analiz sunabilirsin
- Kullanici sohbet sirasinda sunulan SEO onerilerini onaylayip "uygula", "kaydet", "bunu sectim" dediginde uygun alanlarla `save_seo_suggestion` aracini cagir. Bu kayit ikas'a aninda uygulama degildir
- Bir MCP araci GERCEKTEN cagirip basarili sonuc aldiysan, yalnizca o zaman sonucu raporla
- Emin olmadigin bilgiyi uydurma; bilmiyorsan "bilmiyorum" de

Kurallar:
- Turkce yanit ver; kullanici Ingilizce yazarsa Ingilizce yanit ver
- Gerekli degilse MCP cagirisi yapma
- Secili urunun promptta zaten bulunan statik SEO bilgileri icin yeniden arac cagirisi yapma
- SEO onerilerini mevcut skor kirilimlari, sorunlar ve gorunen urun alanlariyla sinirli tut
- Stok, fiyat, kampanya, siparis, musteri, kargo veya operasyonel konulara kullanici acikca istemedikce kendiliginden gecme
- Veri eksigi veya belirsizlik varsa acikca soyle
- Uretim tonu net, profesyonel ve kisa olsun
- Markdown kullanabilirsin
- Genis markdown tablolar yerine kisa listeler kullan; tabloyu yalnizca kullanici isterse kullan

Yaniti mumkunse su duzende kur:
1. Durum (mevcut durumu ozetle)
2. Oneri (somut iyilestirme onerileri sun)
3. Sonraki adim (kullanicinin ne yapmasi gerektigini acikla — ornegin "Bu onerileri uygulamak icin Oneriler panelini kullanabilirsiniz" veya "@ikas ile MCP uzerinden guncelleyebiliriz")

Yeniden yazim istenirse:
- 2 veya 3 alternatif sun
- Alternatiflerin farkini 1 kisa cumleyle belirt
- Bunlarin ONERI oldugunu, otomatik uygulanmadigini belirt

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

ONEMLI — Yetenek sinirlarin:
- @local modunda (arac kullanmadan): Sen SADECE oneri ve analiz sunabilirsin. Hicbir degisikligi uygulayamazsin.
- @ikas modunda (MCP araclariyla): Yalnizca MCP araci GERCEKTEN cagirilip basarili sonuc dondugunde islem yapilmis sayilir.
- Bir MCP araci cagirmadan "guncelledim" veya "uyguladim" DEME. Bu kullaniciyi yaniltir.
- Kullanici degisiklik uygulamak istediginde:
  * @local modundaysan: "Bu onerileri uygulamak icin soldaki panelden ilgili urunu secip 'Oneriler' sekmesinden onaylayabilirsiniz, veya @ikas ile tekrar yazarsaniz MCP uzerinden guncelleyebiliriz" de.
  * @ikas modundaysan: updateProduct mutasyonunu kullanicinin onayiyla cagir ve SONUCUNU raporla.

Davranis kurallari:
- Bu chat ekraninda varsayilan tavsiyeleri yalnizca mevcut SEO metrikleri ve secili urunun eldeki alanlariyla sinirla.
- Operasyon onerisi verirken once secili urunun mevcut kaydini dogrulayan `listProduct` veya SEO alanlarini guncelleyen `updateProduct` etrafinda kal.
- Mutation gerektiren adimlarda kullanicidan net onay iste.
- Arac kullanmiyor olsan bile, nasil ilerlenebilecegini desteklenen operasyon adlariyla kisaca anlat.
- Yanitin sonunda konusmayi ilerletecek tek bir sonraki adim veya soru oner.
- Desteklenmeyen operasyon adi uydurma.
- ASLA gerceklestirmedigin bir islemi basariliymiş gibi raporlama.
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
- ASLA yapmadığın bir işlemi yaptığını iddia etme
- Sen ürünleri doğrudan değiştiremezsin; yalnızca öneri sunabilirsin
- Değişiklik uygulamak için kullanıcıyı uygulamadaki Öneriler paneline veya @ikas MCP moduna yönlendir

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
MATCH_NORMALIZATION_TABLE = str.maketrans({
    "\u00c7": "c",
    "\u00e7": "c",
    "\u011e": "g",
    "\u011f": "g",
    "\u0130": "i",
    "\u0131": "i",
    "\u00d6": "o",
    "\u00f6": "o",
    "\u015e": "s",
    "\u015f": "s",
    "\u00dc": "u",
    "\u00fc": "u",
})
SEO_OPERATION_HINT_PATTERN = re.compile(
    r"\bseo\b|\bskor\b|\bissue\b|\bsorun\b|\boneri\b|\bsuggestion\b|\bmeta\b|\bbaslik\b|\btitle\b|\baciklama\b|\bdescription\b|\bicerik\b|\bcontent\b|\bkeyword\b|\betiket\b|\btag\b|\bkategori\b|\bsku\b|\bokunabilirlik\b|\breadability\b|\bteknik seo\b|\btechnical seo\b|\bisim\b|\bname\b",
    re.IGNORECASE,
)
SUGGESTION_REQUEST_HINT_PATTERN = re.compile(
    r"\boneri\b|\bsuggestion\b|\balternatif\b|\bsecenek\b|\bopsiyon\b|\bvaryant\b|\bvariant\b|\byeniden yaz\b|\brewrite\b|\bolustur\b|\buret\b|\byaz\b|\bhazirla\b",
    re.IGNORECASE,
)
LIVE_PRODUCT_HINT_PATTERNS = (
    STOCK_HINT_PATTERN,
    PRICE_HINT_PATTERN,
    VARIANT_HINT_PATTERN,
)
LIVE_DATA_HINT_PATTERNS = (
    STOCK_HINT_PATTERN,
    PRICE_HINT_PATTERN,
    VARIANT_HINT_PATTERN,
    ORDER_HINT_PATTERN,
    CUSTOMER_HINT_PATTERN,
)
NORMALIZED_LIVE_DATA_HINT_PATTERN = re.compile(
    r"\bstok\b|\benvanter\b|\bkac tane\b|\bkac kaldi\b|\bfiyat\b|\bucret\b|"
    r"\bprice\b|\bvaryant\b|\bvariant\b|\bsiparis\b|\border\b|\bmusteri\b|\bcustomer\b",
    re.IGNORECASE,
)
SEMANTIC_ROUTING_SYSTEM_PROMPT = (
    "Sen bir niyet tespit (intent detection) asistanisin. "
    "Kullanicinin mesaji magazanin canli veritabanindan "
    "(stok, fiyat, siparisler, musteri, varyant) anlik veri cekmeyi "
    "gerektiriyorsa 'true', sadece SEO metin yazarligi, icerik analizi "
    "veya genel bir sohbet ise 'false' don. "
    'SADECE ASAGIDAKI GIBI GECERLI BIR JSON DON: {"needs_mcp": true/false}'
)
SEMANTIC_ROUTING_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

# Patterns that detect when the LLM falsely claims to have performed actions
# These are checked post-response when no MCP mutation was actually executed
FALSE_ACTION_CLAIM_PATTERN = re.compile(
    r"\b(?:"
    r"uygula(?:n)?d[iı]m?|g[uü]ncelle(?:n)?d[iı]m?|de[gğ]i[sş]tird[iı]m?|kaydett[iı]m?|"
    r"ekled[iı]m?|yazd[iı]m|d[uü]zenled[iı]m?|"
    r"applied|updated|saved|changed|modified"
    r")\b",
    re.IGNORECASE,
)
# Patterns for common action confirmation phrases LLMs use
FALSE_ACTION_CONFIRMATION_PATTERN = re.compile(
    r"(?:"
    r"uygulama sonras[iı]|ba[sş]ar[iı]yla (?:uygula|g[uü]ncelle|kayded)|"
    r"i[yı]ile[sş]tirilmi[sş] skor|yeni seo (?:skoru|durumu)|"
    r"yap[iı]lan de[gğ]i[sş]iklikler|g[uü]ncellemeler uyguland[iı]|"
    r"successfully (?:applied|updated|saved)"
    r")",
    re.IGNORECASE,
)

FALSE_ACTION_DISCLAIMER_TR = (
    "\n\n---\n"
    "⚠️ **Not:** Yukarıdaki öneriler henüz uygulanmadı. "
    "Değişiklikleri ikas'a kaydetmek için:\n"
    "- Soldaki panelden ürünü seçip **Öneriler** sekmesinden onaylayın, veya\n"
    "- Mesajınızı **@ikas** ile yazarak MCP üzerinden güncelleyin."
)

SAVE_SEO_SUGGESTION_TOOL_NAME = "save_seo_suggestion"
SUGGESTION_SAVE_SUCCESS_MESSAGE = "\u00d6neri ba\u015far\u0131yla kaydedildi"
SAVE_SEO_SUGGESTION_TOOL_INSTRUCTION = (
    "Kullanici sohbet sirasinda sunulan SEO degisikliklerini onaylayip "
    "'uygula', 'kaydet' veya 'bunu sectim' dediginde "
    "`save_seo_suggestion` aracini cagir. Bu arac degisiklikleri ikas'a "
    "aninda uygulamaz; sadece pending suggestion olarak kaydeder."
)
STRUCTURED_SUGGESTION_OPTIONS_INSTRUCTION = (
    "Eger birden fazla secenek uretiyorsan, yanitinin sonuna "
    "```json\n"
    '[{"tone":"Agresif","value":"..."}]\n'
    "``` "
    "formatinda gizli bir blok ekle. Bu blok yalnizca gecerli bir JSON dizisi icersin."
)
SAVE_SEO_SUGGESTION_FIELD_MAP = {
    "suggested_meta_title": ("meta_title", "suggested_meta_title"),
    "suggested_meta_description": ("meta_desc", "suggested_meta_description"),
    "suggested_description": ("desc_tr", "suggested_description"),
    "suggested_description_en": ("desc_en", "suggested_description_en"),
}


def _build_save_seo_suggestion_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": SAVE_SEO_SUGGESTION_TOOL_NAME,
            "description": (
                "Kullanici sohbet sirasinda sunulan SEO degisikliklerini "
                "(baslik, aciklama vb.) begendiginde ve 'uygula', 'kaydet', "
                "'bunu sectim' dediginde bu araci cagir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "suggested_meta_title": {
                        "type": "string",
                        "description": "Kaydedilecek yeni meta title onerisi.",
                    },
                    "suggested_meta_description": {
                        "type": "string",
                        "description": "Kaydedilecek yeni meta description onerisi.",
                    },
                    "suggested_description": {
                        "type": "string",
                        "description": "Kaydedilecek Turkce urun aciklamasi onerisi.",
                    },
                    "suggested_description_en": {
                        "type": "string",
                        "description": "Kaydedilecek Ingilizce urun aciklamasi onerisi.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    }

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


def _clean_routing_mentions(user_message: str) -> str:
    cleaned = IKAS_MENTION_PATTERN.sub("", user_message)
    cleaned = LOCAL_MENTION_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or user_message.strip()


def _extract_chat_completion_content(data: Any) -> str:
    if not isinstance(data, dict):
        return ""

    choices = data.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""

    choice = choices[0]
    if not isinstance(choice, dict):
        return ""

    message = choice.get("message", {})
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts).strip()
    return ""


def _parse_needs_mcp_flag(content: str) -> bool | None:
    candidate = (content or "").strip()
    if not candidate:
        return None

    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)

    if not candidate.startswith("{"):
        match = SEMANTIC_ROUTING_JSON_PATTERN.search(candidate)
        if not match:
            return None
        candidate = match.group(0)

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    needs_mcp = payload.get("needs_mcp")
    if isinstance(needs_mcp, bool):
        return needs_mcp
    if isinstance(needs_mcp, str):
        normalized = needs_mcp.strip().lower()
        if normalized in {"true", "false"}:
            return normalized == "true"
    return None


def _fallback_needs_mcp(user_message: str) -> bool:
    if any(pattern.search(user_message) for pattern in LIVE_DATA_HINT_PATTERNS):
        return True
    return bool(NORMALIZED_LIVE_DATA_HINT_PATTERN.search(_normalize_matching_text(user_message)))


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


def _normalize_matching_text(text: str) -> str:
    return (text or "").translate(MATCH_NORMALIZATION_TABLE).lower()


def _should_request_structured_suggestion_options(user_message: str) -> bool:
    normalized_text = _normalize_matching_text(user_message)
    return bool(
        normalized_text
        and SEO_OPERATION_HINT_PATTERN.search(normalized_text)
        and SUGGESTION_REQUEST_HINT_PATTERN.search(normalized_text)
    )


def _operation_footer_already_present(text: str) -> bool:
    return "ikas mcp operasyon onerisi" in _normalize_matching_text(text)


def _select_product_operation_suggestion(
    user_message: str,
    response_text: str,
    product: Product | None,
) -> tuple[str, str, bool]:
    normalized_text = _normalize_matching_text(f"{user_message}\n{response_text}")
    product_label = (product.name or "").strip() if product else ""
    subject = product_label or "secili urun"

    if SEO_OPERATION_HINT_PATTERN.search(normalized_text):
        return (
            "updateProduct",
            f"{subject} icin mevcut baslik, aciklama, meta ve diger SEO alanlarini guncellemek icin uygun adim",
            True,
        )

    return (
        "listProduct",
        f"{subject} kaydini dogrulamak ve eldeki urun alanlarini netlestirmek icin uygun query",
        False,
    )


def _append_operation_suggestion(
    response_text: str,
    *,
    user_message: str,
    product: Product | None,
) -> str:
    content = (response_text or "").strip()
    if not content or _operation_footer_already_present(content):
        return response_text

    operation_name, reason, requires_confirmation = _select_product_operation_suggestion(
        user_message,
        content,
        product,
    )

    lines = [
        content,
        "",
        "**ikas MCP Operasyon Onerisi**",
        f"- `{operation_name}`: {reason}.",
    ]
    if requires_confirmation:
        lines.append("- Not: Bu bir mutation adimidir; uygulamadan once onayini alirim.")
    lines.append("- Istersen bir sonraki adimda bunu secili urun icin netlestireyim.")
    return "\n".join(lines)


def _has_mutation_tool_result(tool_results: list[dict[str, Any]]) -> bool:
    """Check if any tool result is from a mutation (write) operation."""
    mutation_prefixes = ("update", "create", "delete", "save", "add", "remove", "fulfill", "cancel", "refund", "approve")
    for result in tool_results:
        tool_name = str(result.get("tool", "")).strip()
        if any(tool_name.startswith(prefix) for prefix in mutation_prefixes):
            # Check that the result doesn't contain an error
            result_text = str(result.get("result", ""))
            if '"error"' not in result_text:
                return True
    return False


def _append_false_action_disclaimer(
    response_text: str,
    tool_results: list[dict[str, Any]],
) -> str:
    """Append a disclaimer if the LLM claims to have applied changes but no mutation was executed.

    Small local models often hallucinate action confirmations like "Güncellemeler uygulandı!"
    when they haven't actually called any MCP tool. This function detects such false claims
    and appends a visible disclaimer to prevent user confusion.
    """
    if not response_text:
        return response_text

    # If a mutation was actually executed successfully, the claim is legitimate
    if _has_mutation_tool_result(tool_results):
        return response_text

    # Check for false action claims in the response
    has_false_claim = (
        FALSE_ACTION_CLAIM_PATTERN.search(response_text)
        or FALSE_ACTION_CONFIRMATION_PATTERN.search(response_text)
    )

    if not has_false_claim:
        return response_text

    # Already has a disclaimer
    if "henüz uygulanmadı" in response_text or "henuz uygulanmadi" in response_text:
        return response_text

    return response_text + FALSE_ACTION_DISCLAIMER_TR


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


def _extract_stream_delta_content(delta: dict[str, Any]) -> str:
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return ""


class _StreamingVisibleTextFilter:
    """Hide <think> blocks while still streaming visible assistant text."""

    _OPEN_TAG = "<think>"
    _CLOSE_TAG = "</think>"

    def __init__(self) -> None:
        self._inside_think = False
        self._pending_tag = ""

    def consume(self, chunk: str) -> str:
        if not chunk:
            return ""

        text = f"{self._pending_tag}{chunk}"
        self._pending_tag = ""
        visible_parts: list[str] = []
        index = 0

        while index < len(text):
            remainder = text[index:]
            if remainder.startswith(self._OPEN_TAG):
                self._inside_think = True
                index += len(self._OPEN_TAG)
                continue
            if remainder.startswith(self._CLOSE_TAG):
                self._inside_think = False
                index += len(self._CLOSE_TAG)
                continue

            if text[index] == "<":
                partial_tag = self._match_partial_tag(remainder)
                if partial_tag is not None:
                    self._pending_tag = partial_tag
                    break

            if not self._inside_think:
                visible_parts.append(text[index])
            index += 1

        return "".join(visible_parts)

    def finalize(self) -> str:
        if self._inside_think or not self._pending_tag:
            self._pending_tag = ""
            return ""

        trailing_text = self._pending_tag
        self._pending_tag = ""
        return trailing_text

    @classmethod
    def _match_partial_tag(cls, text: str) -> str | None:
        for tag in (cls._OPEN_TAG, cls._CLOSE_TAG):
            if tag.startswith(text) and text != tag:
                return text
        return None


def _merge_stream_tool_call(
    tool_calls_by_index: dict[int, dict[str, Any]],
    tool_call_delta: dict[str, Any],
) -> None:
    raw_index = tool_call_delta.get("index", 0)
    index = raw_index if isinstance(raw_index, int) else 0
    tool_call = tool_calls_by_index.setdefault(index, {
        "id": "",
        "type": "function",
        "function": {
            "name": "",
            "arguments": "",
        },
    })

    tool_call_id = tool_call_delta.get("id")
    if isinstance(tool_call_id, str) and tool_call_id:
        tool_call["id"] = tool_call_id

    tool_call_type = tool_call_delta.get("type")
    if isinstance(tool_call_type, str) and tool_call_type:
        tool_call["type"] = tool_call_type

    function_delta = tool_call_delta.get("function", {})
    if not isinstance(function_delta, dict):
        return

    function_payload = tool_call.setdefault("function", {"name": "", "arguments": ""})
    name = function_delta.get("name")
    if isinstance(name, str) and name:
        function_payload["name"] = f"{function_payload.get('name', '')}{name}"

    arguments = function_delta.get("arguments")
    if isinstance(arguments, str) and arguments:
        function_payload["arguments"] = f"{function_payload.get('arguments', '')}{arguments}"


def _merge_stream_meta_payload(target: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(target)

    model_name = payload.get("model")
    if isinstance(model_name, str) and model_name:
        merged["model"] = model_name

    for key in ("usage", "stats", "model_info", "stop_reason"):
        value = payload.get(key)
        if value not in (None, "", {}, []):
            merged[key] = value

    return merged


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
        self._history_summary_lock = asyncio.Lock()
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

    async def _summarize_and_compress_history(self) -> None:
        async with self._history_summary_lock:
            if len(self._history) <= HISTORY_SUMMARY_TRIGGER_MESSAGES:
                return

            messages_to_summarize = list(self._history[:-HISTORY_SUMMARY_KEEP_RECENT_MESSAGES])
            if not messages_to_summarize:
                return

            history_block = "\n\n".join(
                f"role: {msg.role}\ncontent: {msg.content}"
                for msg in messages_to_summarize
            ).strip()
            if not history_block:
                return

            base_url = self._get_base_url()
            model = self._config.ai_model_name or self._get_default_model()
            request_body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": MEMORY_SUMMARIZATION_PROMPT},
                    {"role": "user", "content": history_block},
                ],
                "temperature": 0.2,
                "max_tokens": max(128, min(self._config.ai_max_tokens, 256)),
                "stream": False,
            }
            timeout = (
                httpx.Timeout(60.0, connect=10.0)
                if self._config.ai_provider in ("ollama", "lm-studio")
                else httpx.Timeout(30.0, connect=10.0)
            )
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._config.ai_api_key:
                headers["Authorization"] = f"Bearer {self._config.ai_api_key}"

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{base_url}/chat/completions",
                        json=request_body,
                        headers=headers,
                    )
                    response.raise_for_status()
                    payload = response.json()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("History summarization failed", exc_info=True)
                return

            summary = self._remove_thinking(_extract_chat_completion_content(payload)).strip()
            if not summary:
                return

            current_history = list(self._history)
            summarized_count = len(messages_to_summarize)
            if len(current_history) < summarized_count:
                return
            if current_history[:summarized_count] != messages_to_summarize:
                return

            summary_message = ChatMessage(
                role="system",
                content=f"{HISTORY_SUMMARY_SYSTEM_PREFIX}{summary}",
            )
            self._history = [summary_message, *current_history[summarized_count:]]

    def _schedule_history_summarization(self) -> None:
        asyncio.create_task(self._summarize_and_compress_history())

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

    async def _get_routing_mode(self, user_message: str) -> bool:
        has_ikas = bool(IKAS_MENTION_PATTERN.search(user_message))
        has_local = bool(LOCAL_MENTION_PATTERN.search(user_message))

        if has_ikas and not has_local:
            return True
        if has_local and not has_ikas:
            return False

        cleaned_message = _clean_routing_mentions(user_message)
        if not cleaned_message:
            return False

        base_url = self._get_base_url()
        model = self._config.ai_model_name or self._get_default_model()
        request_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SEMANTIC_ROUTING_SYSTEM_PROMPT},
                {"role": "user", "content": cleaned_message},
            ],
            "temperature": 0.0,
            "max_tokens": 15,
            "stream": False,
        }
        timeout = (
            httpx.Timeout(60.0, connect=10.0)
            if self._config.ai_provider in ("ollama", "lm-studio")
            else httpx.Timeout(30.0, connect=10.0)
        )
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.ai_api_key:
            headers["Authorization"] = f"Bearer {self._config.ai_api_key}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                with self._active_request_lock:
                    self._active_http_client = client
                try:
                    response = await client.post(
                        f"{base_url}/chat/completions",
                        json=request_body,
                        headers=headers,
                    )
                    response.raise_for_status()
                    payload = response.json()
                finally:
                    with self._active_request_lock:
                        if self._active_http_client is client:
                            self._active_http_client = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Semantic routing request failed: %s", exc)
            return _fallback_needs_mcp(cleaned_message)

        completion_text = _extract_chat_completion_content(payload)
        needs_mcp = _parse_needs_mcp_flag(completion_text)
        if needs_mcp is not None:
            return needs_mcp

        logger.warning("Semantic routing returned invalid payload: %s", completion_text[:200])
        return _fallback_needs_mcp(cleaned_message)

    async def _extract_message_directives(
        self,
        user_message: str,
    ) -> tuple[str, str | None, bool]:
        """Parse routing hints into instructions for the main completion."""
        cleaned_message = _clean_routing_mentions(user_message)
        allow_tools = await self._get_routing_mode(user_message)

        has_ikas = bool(IKAS_MENTION_PATTERN.search(user_message))
        has_local = bool(LOCAL_MENTION_PATTERN.search(user_message))

        if allow_tools:
            if has_ikas and has_local:
                intro = (
                    "Bu mesaj hem @ikas hem @local ile etiketlendi; semantic routing "
                    "canli veri gerektigine karar verdi. "
                )
            elif has_ikas:
                intro = "Bu mesaj @ikas ile etiketlendi. "
            else:
                intro = (
                    "Semantic routing bu mesaj icin canli magaza verisine "
                    "ihtiyac oldugunu tespit etti. "
                )

            return (
                cleaned_message,
                (
                    f"{intro}"
                    "Mumkunse uygun bir ikas MCP araci kullanmadan yanit verme. "
                    "Canli veri cekemiyorsan bunu acikca belirt. "
                    "Yanitta tavsiyeyi yine mevcut SEO problemi ve secili urun baglami etrafinda tut. "
                    "Operasyon onerisi gerekiyorsa once `listProduct`, gerekiyorsa `updateProduct` oner; mutation gerekiyorsa onay iste. "
                    "ONEMLI: Yalnizca MCP araci gercekten cagirilip basarili sonuc dondugunde islemi raporla. Arac cagirmadan 'guncelledim' deme."
                ),
                True,
            )

        if has_ikas and has_local:
            intro = (
                "Bu mesaj hem @ikas hem @local ile etiketlendi; semantic routing "
                "arac kullanmaya gerek gormedi. "
            )
        elif has_local:
            intro = "Bu mesaj @local ile etiketlendi. "
        else:
            intro = (
                "Semantic routing bu mesajin mevcut baglam ve SEO metin "
                "yazarligi ile yanitlanabilecegini tespit etti. "
            )

        return (
            cleaned_message,
            (
                f"{intro}"
                "ikas MCP araci kullanma; yalnizca mevcut SEO metrikleri, secili urunun promptta bulunan alanlari ve sohbet baglamina gore yanit ver. "
                "Stok, fiyat, siparis, kampanya veya musteri verisi uydurma. "
                "Kullanici urun aciklamasi, meta title veya meta description gibi mevcut alanlari yorumlamani isterse bunu local baglamla yap. "
                "KRITIK: Bu modda ikas'a dogrudan degisiklik uygulayamazsin. Kullanici sohbet sirasinda sunulan SEO onerilerini onaylarsa "
                "`save_seo_suggestion` araciyla pending suggestion kaydi olusturabilirsin. "
                "Uygun oldugunda @ikas ile MCP uzerinden veya uygulamadaki Oneriler paneliyle nasil ilerlenebilecegini oner."
            ),
            False,
        )

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

    def _build_chat_tools(
        self,
        *,
        allow_mcp_tools: bool,
        guided_context: str,
        user_message: str,
    ) -> tuple[list[dict[str, Any]] | None, list[str]]:
        tools: list[dict[str, Any]] = [_build_save_seo_suggestion_tool()]
        instructions: list[str] = []

        instructions.append(SAVE_SEO_SUGGESTION_TOOL_INSTRUCTION)

        if allow_mcp_tools and self._mcp_initialized and self._mcp and not guided_context:
            tools.extend(self._mcp.get_tools_as_openai_functions())
            tool_catalog_instruction = _build_tool_catalog_instruction(self.mcp_tools, user_message)
            if tool_catalog_instruction:
                instructions.append(tool_catalog_instruction)

        return (tools or None), instructions

    def _save_suggestion_from_tool_args(
        self,
        args: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None]:
        from core.suggestion_service import apply_suggestion_field, create_pending_suggestion
        from data import db

        if not self._product:
            return json.dumps({
                "ok": False,
                "error": "Secili urun olmadan oneri kaydedilemez.",
            }, ensure_ascii=False), None

        suggestion = create_pending_suggestion(self._product)
        saved_fields: dict[str, str] = {}

        for arg_key, (field_name, attr_name) in SAVE_SEO_SUGGESTION_FIELD_MAP.items():
            raw_value = args.get(arg_key)
            if not isinstance(raw_value, str) or not raw_value.strip():
                continue

            apply_suggestion_field(suggestion, field_name, raw_value)
            cleaned_value = getattr(suggestion, attr_name, "") or ""
            if isinstance(cleaned_value, str) and cleaned_value.strip():
                saved_fields[arg_key] = cleaned_value

        if not saved_fields:
            return json.dumps({
                "ok": False,
                "error": "Kaydedilecek gecerli bir SEO onerisi bulunamadi.",
            }, ensure_ascii=False), None

        db.save_or_update_pending_suggestion(suggestion)
        suggestion_saved = {
            "product_id": self._product.id,
            "product_name": self._product.name,
            "fields": saved_fields,
        }
        return json.dumps({
            "ok": True,
            "message": SUGGESTION_SAVE_SUCCESS_MESSAGE,
            "suggestion_saved": suggestion_saved,
        }, ensure_ascii=False), suggestion_saved

    async def _execute_chat_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None]:
        if tool_name == SAVE_SEO_SUGGESTION_TOOL_NAME:
            return self._save_suggestion_from_tool_args(args)

        if self._mcp and self._mcp_initialized:
            try:
                result = await self._mcp.call_tool(tool_name, args)
                return json.dumps(result, ensure_ascii=False, indent=2), None
            except Exception as exc:
                return json.dumps({
                    "error": str(exc),
                    "available_tools": self._mcp.get_tool_names(),
                }, ensure_ascii=False), None

        return json.dumps({
            "error": f"Tool '{tool_name}' is not available.",
            "available_tools": [SAVE_SEO_SUGGESTION_TOOL_NAME],
        }, ensure_ascii=False), None

    async def send_message(self, user_message: str) -> ChatResponse:
        """Send a user message and get an AI response."""
        return await self._run_message_flow(user_message)

    async def stream_message(self, user_message: str) -> AsyncIterator[dict[str, Any]]:
        """Stream chat chunks followed by a final response payload."""
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def emit_chunk(chunk: str) -> None:
            if not chunk:
                return
            await queue.put({
                "type": "chunk",
                "content": chunk,
            })

        async def runner() -> ChatResponse:
            try:
                return await self._run_message_flow(user_message, chunk_handler=emit_chunk)
            finally:
                await queue.put(None)

        task = asyncio.create_task(runner())

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event

            response = await task
        except asyncio.CancelledError:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
            raise
        except Exception:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
            raise

        yield self._build_response_done_event(response)

    async def _run_message_flow(
        self,
        user_message: str,
        chunk_handler: Callable[[str], Awaitable[None]] | None = None,
    ) -> ChatResponse:
        """Run the full chat flow, optionally streaming assistant chunks."""
        cleaned_message, routing_instruction, allow_tools = await self._extract_message_directives(user_message)
        explicit_ikas_mode = bool(IKAS_MENTION_PATTERN.search(user_message)) and not bool(
            LOCAL_MENTION_PATTERN.search(user_message)
        )

        # Add user message to history
        user_msg = ChatMessage(role="user", content=cleaned_message)
        self._history.append(user_msg)

        # Trim history if too long
        if len(self._history) > MAX_HISTORY_MESSAGES:
            self._history = self._history[-MAX_HISTORY_MESSAGES:]

        # Build messages for the AI
        system_prompt = _build_product_context(self._product, self._score)
        if _should_request_structured_suggestion_options(cleaned_message):
            system_prompt = (
                f"{system_prompt}\n\n{STRUCTURED_SUGGESTION_OPTIONS_INSTRUCTION}"
            )
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
                if explicit_ikas_mode:
                    guided_content = _append_operation_suggestion(
                        guided_fallback,
                        user_message=cleaned_message,
                        product=self._product,
                    )
                    assistant_msg = ChatMessage(role="assistant", content=guided_content)
                    self._history.append(assistant_msg)
                    response = ChatResponse(
                        content=guided_content,
                        thinking="",
                        tool_results=guided_tool_results,
                        error=False,
                        meta={
                            "model": "ikas MCP",
                            "finish_reason": "guided_mcp",
                            "source": "ikas_mcp",
                        },
                    )
                    if chunk_handler and response.content:
                        await chunk_handler(response.content)
                    self._schedule_history_summarization()
                    return response
                messages.append({
                    "role": "system",
                    "content": (
                        "Asagidaki ikas MCP sonucu dogrulanmis canli veridir. "
                        "Bu veriyi esas al, veri uydurma ve degistirme:\n"
                        f"{guided_context}"
                    ),
                })
        elif allow_tools:
            messages.append({
                "role": "system",
                "content": (
                    "ikas MCP su anda hazir degil. Canli veri cekemedigini acikca belirt "
                    "ve magaza verisi uydurma."
                ),
            })

        tools, tool_instructions = self._build_chat_tools(
            allow_mcp_tools=allow_tools,
            guided_context=guided_context,
            user_message=cleaned_message,
        )
        for instruction in tool_instructions:
            messages.append({
                "role": "system",
                "content": instruction,
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

        response_text = ""
        thinking_text = ""
        tool_results: list[dict[str, Any]] = list(guided_tool_results)
        meta: dict[str, Any] = {}
        suggestion_saved: dict[str, Any] | None = None

        try:
            if chunk_handler is None:
                completion_result = await self._chat_completion(messages, tools)
            else:
                completion_result = await self._chat_completion_stream(
                    messages,
                    tools,
                    chunk_handler,
                )
            response_text, thinking_text, completion_tool_results, meta, suggestion_saved = (
                self._normalize_completion_result(completion_result)
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
                guided_content = _append_operation_suggestion(
                    guided_fallback,
                    user_message=cleaned_message,
                    product=self._product,
                )
                assistant_msg = ChatMessage(role="assistant", content=guided_content)
                self._history.append(assistant_msg)
                response = ChatResponse(
                    content=guided_content,
                    thinking="",
                    tool_results=tool_results,
                    error=False,
                    meta={
                        "model": "ikas MCP",
                        "finish_reason": "guided_mcp_fallback",
                        "source": "ikas_mcp",
                    },
                )
                if chunk_handler and response.content:
                    await chunk_handler(response.content)
                self._schedule_history_summarization()
                return response

            response = ChatResponse(
                content=_append_operation_suggestion(
                    _format_chat_error(exc),
                    user_message=cleaned_message,
                    product=self._product,
                ),
                thinking="",
                tool_results=tool_results,
                error=True,
                meta={},
            )
            if chunk_handler and response.content:
                await chunk_handler(response.content)
            self._schedule_history_summarization()
            return response

        if not response_text and guided_fallback:
            response_text = guided_fallback
        elif not response_text.strip() and thinking_text:
            response_text = (
                "Model nihai cevap uretmedi. Yerel model dusunce modunda takilmis olabilir; "
                "daha kisa bir istek deneyin veya Thinking Mode'u kapatin."
            )
        elif suggestion_saved:
            response_text = SUGGESTION_SAVE_SUCCESS_MESSAGE

        if not suggestion_saved:
            response_text = _append_operation_suggestion(
                response_text,
                user_message=cleaned_message,
                product=self._product,
            )
            response_text = _append_false_action_disclaimer(response_text, tool_results)

        assistant_msg = ChatMessage(role="assistant", content=response_text)
        self._history.append(assistant_msg)
        self._schedule_history_summarization()

        return ChatResponse(
            content=response_text,
            thinking=thinking_text,
            tool_results=tool_results,
            error=False,
            meta=meta,
            suggestion_saved=suggestion_saved,
        )

    async def _chat_completion_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        chunk_handler: Callable[[str], Awaitable[None]],
    ) -> tuple[str, str, list[dict], dict, dict[str, Any] | None]:
        """Consume the streaming completion generator and forward text chunks."""
        final_event: dict[str, Any] | None = None

        async for event in self.async_stream_chat(messages, tools):
            if event.get("type") == "chunk":
                chunk = str(event.get("content") or "")
                if chunk:
                    await chunk_handler(chunk)
                continue

            if event.get("type") == "completion_result":
                final_event = event

        if final_event is None:
            raise RuntimeError("Chat completion stream ended without a final result.")

        return (
            str(final_event.get("content") or ""),
            str(final_event.get("thinking") or ""),
            list(final_event.get("tool_results") or []),
            dict(final_event.get("meta") or {}),
            dict(final_event.get("suggestion_saved") or {}) or None,
        )

    @staticmethod
    def _build_response_done_event(response: ChatResponse) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "response_done",
            "content": response.content,
            "thinking": response.thinking,
            "tool_results": response.tool_results,
            "error": response.error,
            "meta": response.meta,
        }
        if response.suggestion_saved:
            payload["suggestion_saved"] = response.suggestion_saved
        return payload

    @staticmethod
    def _normalize_completion_result(
        result: Any,
    ) -> tuple[str, str, list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
        if not isinstance(result, tuple):
            raise TypeError("Chat completion must return a tuple.")

        if len(result) == 4:
            response_text, thinking_text, tool_results, meta = result
            suggestion_saved = None
        elif len(result) == 5:
            response_text, thinking_text, tool_results, meta, suggestion_saved = result
        else:
            raise ValueError("Unexpected chat completion result shape.")

        return (
            str(response_text or ""),
            str(thinking_text or ""),
            list(tool_results or []),
            dict(meta or {}),
            dict(suggestion_saved or {}) or None,
        )

    async def async_stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat completion chunks and resolve tool calls when needed."""
        base_url = self._get_base_url()
        model = self._config.ai_model_name or self._get_default_model()
        all_tool_results: list[dict[str, Any]] = []
        last_message_content = ""
        last_meta: dict[str, Any] = {}
        last_suggestion_saved: dict[str, Any] | None = None

        for _round in range(MAX_TOOL_ROUNDS):
            request_body: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": self._config.ai_temperature,
                "max_tokens": self._config.ai_max_tokens,
                "stream": True,
            }

            if tools and self._config.ai_provider in ("ollama", "lm-studio", "openai", "openrouter", "custom"):
                request_body["tools"] = tools

            timeout = (
                httpx.Timeout(600.0, connect=10.0)
                if self._config.ai_provider in ("ollama", "lm-studio")
                else httpx.Timeout(120.0, connect=10.0)
            )
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._config.ai_api_key:
                headers["Authorization"] = f"Bearer {self._config.ai_api_key}"

            message_content = ""
            finish_reason = "stop"
            meta_payload: dict[str, Any] = {"model": model}
            tool_calls: list[dict[str, Any]] = []
            streamed_chunk_emitted = False
            tool_calls_by_index: dict[int, dict[str, Any]] = {}
            visible_text_filter = _StreamingVisibleTextFilter()

            async with httpx.AsyncClient(timeout=timeout) as client:
                with self._active_request_lock:
                    self._active_http_client = client
                try:
                    async with client.stream(
                        "POST",
                        f"{base_url}/chat/completions",
                        json=request_body,
                        headers=headers,
                    ) as resp:
                        resp.raise_for_status()
                        content_type = resp.headers.get("content-type", "").lower()

                        if "text/event-stream" not in content_type:
                            data = json.loads((await resp.aread()).decode("utf-8"))
                            meta_payload = _merge_stream_meta_payload(meta_payload, data)
                            choice = data.get("choices", [{}])[0]
                            message = choice.get("message", {}) if isinstance(choice, dict) else {}
                            finish_reason = choice.get("finish_reason", "stop") if isinstance(choice, dict) else "stop"
                            message_content = str(message.get("content") or "")
                            raw_tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
                            if isinstance(raw_tool_calls, list):
                                tool_calls = raw_tool_calls
                        else:
                            pending_data_lines: list[str] = []
                            sse_event_name = ""
                            # Non-delta LM Studio native event names that carry no text content
                            _LM_STUDIO_NON_CONTENT_EVENTS = frozenset({
                                "chat.start", "chat.end",
                                "model_load.start", "model_load.progress", "model_load.end",
                                "prompt_processing.start", "prompt_processing.progress",
                                "prompt_processing.end",
                                "reasoning.start", "reasoning.end",
                                "tool_call.start", "tool_call.arguments",
                                "tool_call.success", "tool_call.failure",
                                "message.start", "message.end",
                                "error",
                            })
                            async for line in resp.aiter_lines():
                                if not line:
                                    if not pending_data_lines:
                                        sse_event_name = ""
                                        continue
                                    event_data = "\n".join(pending_data_lines)
                                    pending_data_lines.clear()
                                    current_sse_event = sse_event_name
                                    sse_event_name = ""
                                    if event_data == "[DONE]":
                                        break
                                    try:
                                        data = json.loads(event_data)
                                    except json.JSONDecodeError:
                                        logger.debug("Skipping invalid SSE payload: %s", event_data[:200])
                                        continue

                                    meta_payload = _merge_stream_meta_payload(meta_payload, data)
                                    choices = data.get("choices", [])
                                    if not isinstance(choices, list) or not choices:
                                        # Fallback: handle LM Studio native streaming format where
                                        # the compat endpoint returns {"content": "..."} payloads
                                        # (event: message.delta) instead of OpenAI choices structure.
                                        if current_sse_event not in _LM_STUDIO_NON_CONTENT_EVENTS:
                                            native_content = data.get("content")
                                            if isinstance(native_content, str) and native_content:
                                                message_content += native_content
                                                visible_chunk = visible_text_filter.consume(native_content)
                                                if visible_chunk and not tool_calls_by_index:
                                                    streamed_chunk_emitted = True
                                                    yield {
                                                        "type": "chunk",
                                                        "content": visible_chunk,
                                                    }
                                        continue

                                    choice = choices[0]
                                    if not isinstance(choice, dict):
                                        continue

                                    delta = choice.get("delta", {})
                                    if not isinstance(delta, dict):
                                        delta = {}

                                    raw_finish_reason = choice.get("finish_reason")
                                    if isinstance(raw_finish_reason, str) and raw_finish_reason:
                                        finish_reason = raw_finish_reason

                                    chunk = _extract_stream_delta_content(delta)
                                    if chunk:
                                        message_content += chunk
                                        visible_chunk = visible_text_filter.consume(chunk)
                                        if visible_chunk and not tool_calls_by_index:
                                            streamed_chunk_emitted = True
                                            yield {
                                                "type": "chunk",
                                                "content": visible_chunk,
                                            }

                                    delta_tool_calls = delta.get("tool_calls")
                                    if isinstance(delta_tool_calls, list):
                                        for tool_call_delta in delta_tool_calls:
                                            if isinstance(tool_call_delta, dict):
                                                _merge_stream_tool_call(tool_calls_by_index, tool_call_delta)
                                    continue

                                if line.startswith(":"):
                                    continue
                                if line.startswith("event:"):
                                    sse_event_name = line[6:].strip()
                                    continue
                                if line.startswith("data:"):
                                    pending_data_lines.append(line[5:].lstrip())

                            if pending_data_lines:
                                event_data = "\n".join(pending_data_lines)
                                if event_data != "[DONE]":
                                    try:
                                        data = json.loads(event_data)
                                    except json.JSONDecodeError:
                                        logger.debug("Skipping trailing SSE payload: %s", event_data[:200])
                                    else:
                                        meta_payload = _merge_stream_meta_payload(meta_payload, data)
                                        choices = data.get("choices", [])
                                        if isinstance(choices, list) and choices:
                                            choice = choices[0]
                                            if isinstance(choice, dict):
                                                delta = choice.get("delta", {})
                                                if not isinstance(delta, dict):
                                                    delta = {}
                                                raw_finish_reason = choice.get("finish_reason")
                                                if isinstance(raw_finish_reason, str) and raw_finish_reason:
                                                    finish_reason = raw_finish_reason
                                                chunk = _extract_stream_delta_content(delta)
                                                if chunk:
                                                    message_content += chunk
                                                    visible_chunk = visible_text_filter.consume(chunk)
                                                    if visible_chunk and not tool_calls_by_index:
                                                        streamed_chunk_emitted = True
                                                        yield {
                                                            "type": "chunk",
                                                            "content": visible_chunk,
                                                        }
                                                delta_tool_calls = delta.get("tool_calls")
                                                if isinstance(delta_tool_calls, list):
                                                    for tool_call_delta in delta_tool_calls:
                                                        if isinstance(tool_call_delta, dict):
                                                            _merge_stream_tool_call(tool_calls_by_index, tool_call_delta)
                finally:
                    with self._active_request_lock:
                        if self._active_http_client is client:
                            self._active_http_client = None

            if not tool_calls and tool_calls_by_index:
                tool_calls = [tool_calls_by_index[index] for index in sorted(tool_calls_by_index)]

            trailing_visible_chunk = visible_text_filter.finalize()
            if trailing_visible_chunk and not tool_calls and not tool_calls_by_index:
                streamed_chunk_emitted = True
                yield {
                    "type": "chunk",
                    "content": trailing_visible_chunk,
                }

            meta = _build_completion_meta(meta_payload, model, finish_reason)
            self._total_tokens["input"] += int(meta.get("input_tokens", 0) or 0)
            self._total_tokens["output"] += int(meta.get("output_tokens", 0) or 0)

            last_message_content = message_content
            last_meta = meta

            if tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": message_content,
                    "tool_calls": tool_calls,
                })

                for tc in tool_calls:
                    func = tc.get("function", {}) if isinstance(tc, dict) else {}
                    tool_name = func.get("name", "") if isinstance(func, dict) else ""
                    try:
                        args = json.loads(func.get("arguments", "{}")) if isinstance(func, dict) else {}
                    except json.JSONDecodeError:
                        args = {}
                    if not isinstance(args, dict):
                        args = {}

                    result_text, suggestion_saved = await self._execute_chat_tool(tool_name, args)
                    if suggestion_saved:
                        last_suggestion_saved = suggestion_saved

                    tool_result = {
                        "tool": tool_name,
                        "arguments": args,
                        "result": result_text[:2000],
                    }
                    all_tool_results.append(tool_result)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", "") if isinstance(tc, dict) else "",
                        "name": tool_name,
                        "content": result_text,
                    })

                if last_suggestion_saved:
                    confirmation_message = SUGGESTION_SAVE_SUCCESS_MESSAGE
                    yield {
                        "type": "chunk",
                        "content": confirmation_message,
                    }
                    yield {
                        "type": "completion_result",
                        "content": confirmation_message,
                        "thinking": "",
                        "tool_results": list(all_tool_results),
                        "meta": {
                            **meta,
                            "source": "suggestion_saved",
                        },
                        "suggestion_saved": last_suggestion_saved,
                    }
                    return

                continue

            thinking_text = self._extract_thinking(message_content)
            response_text = self._remove_thinking(message_content) if thinking_text else message_content

            if response_text and not streamed_chunk_emitted:
                yield {
                    "type": "chunk",
                    "content": response_text,
                }

            yield {
                "type": "completion_result",
                "content": response_text,
                "thinking": thinking_text,
                "tool_results": list(all_tool_results),
                "meta": meta,
                "suggestion_saved": last_suggestion_saved,
            }
            return

        yield {
            "type": "completion_result",
            "content": last_message_content or "Maksimum arac cagrisi sayisina ulasildi.",
            "thinking": "",
            "tool_results": list(all_tool_results),
            "meta": last_meta,
            "suggestion_saved": last_suggestion_saved,
        }

    async def _chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> tuple[str, str, list[dict], dict, dict[str, Any] | None]:
        """Run chat completion with automatic tool-call handling."""
        final_event: dict[str, Any] | None = None

        async for event in self.async_stream_chat(messages, tools):
            if event.get("type") == "completion_result":
                final_event = event

        if final_event is None:
            return "", "", [], {}, None

        return (
            str(final_event.get("content") or ""),
            str(final_event.get("thinking") or ""),
            list(final_event.get("tool_results") or []),
            dict(final_event.get("meta") or {}),
            dict(final_event.get("suggestion_saved") or {}) or None,
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

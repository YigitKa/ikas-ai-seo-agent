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
- Kullanici "uygula", "kaydet", "secenek X uygula" gibi bir istek yaptiginda sistem bunu otomatik algilar ve sohbetteki onerileri DB'ye kaydeder. Sen sadece oneri sun, uygulama islemini kendin yaptigini iddia etme
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
LIVE_PRODUCT_HINT_PATTERNS = (
    STOCK_HINT_PATTERN,
    PRICE_HINT_PATTERN,
    VARIANT_HINT_PATTERN,
)

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

# Detect user intent to apply/save suggestions from chat
APPLY_INTENT_PATTERN = re.compile(
    r"(?:^|\b)(?:"
    r"(?:bunu?\s+)?(?:uygula|kaydet|onayla|se[cç]enek\s*[a-cA-C]\s*(?:uygula|kaydet|se[cç]))|"
    r"(?:se[cç]enek\s*[a-cA-C]'?[yıiu]?\s+(?:uygula|kaydet|se[cç]))|"
    r"(?:bu\s+(?:[oö]neri(?:yi|leri)?|de[gğ]i[sş]ikli[gğ]i)\s*(?:uygula|kaydet|onayla))|"
    r"(?:(?:hepsini|t[uü]m[uü]n[uü])\s*(?:uygula|kaydet))|"
    r"apply|save\s+(?:this|these|suggestion)"
    r")\b",
    re.IGNORECASE,
)

# System prompt for extracting structured suggestion data from conversation
SUGGESTION_EXTRACTION_PROMPT = """Asagidaki sohbet gecmisinden secili urune onerilen degisiklikleri JSON olarak cikar.
Yalnizca ACIKCA onerilmis alanlari dahil et. Onerilmemis alanlari bos birak.
Birden fazla alternatif varsa, kullanicinin son sectigi veya en son onerileni kullan.

SADECE su JSON formatini dondur, baska hicbir sey yazma:
{"suggested_meta_title": "", "suggested_meta_description": "", "suggested_name": "", "suggested_description": "", "suggested_description_en": ""}

Kurallar:
- Deger onerilmemisse bos string birak
- HTML etiketi ekleme
- Sadece JSON dondur, aciklama ekleme"""

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
                "Yanitini once mevcut SEO metrikleri ve eldeki urun alanlariyla sinirla. "
                "Canli veri ancak kullanicinin acik talebiyle gerekiyorsa uygun bir ikas MCP araci kullan, sonra sonucu kisa ve net bicimde yorumla. "
                "Gerekirse `listProduct` veya `updateProduct` etrafinda sonraki adimi oner; mutation icin onay iste. "
                "ONEMLI: Bir MCP araci gercekten cagirmadan 'guncelledim' veya 'uyguladim' deme."
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
                "Yanitta tavsiyeyi yine mevcut SEO problemi ve secili urun baglami etrafinda tut. "
                "Operasyon onerisi gerekiyorsa once `listProduct`, gerekiyorsa `updateProduct` oner; mutation gerekiyorsa onay iste. "
                "ONEMLI: Yalnizca MCP araci gercekten cagirilip basarili sonuc dondugunde islemi raporla. Arac cagirmadan 'guncelledim' deme."
            ),
            True,
        )

    if routing_mode == "local":
        return (
            cleaned_message,
            (
                "Bu mesaj @local ile etiketlendi veya mention icermiyor. "
                "Arac kullanma; yalnizca mevcut SEO metrikleri, secili urunun promptta bulunan alanlari ve sohbet baglamina gore yanit ver. "
                "Stok, fiyat, siparis, kampanya veya musteri verisi uydurma. "
                "Kullanici urun aciklamasi, meta title veya meta description gibi mevcut alanlari yorumlamani isterse bunu local baglamla yap. "
                "KRITIK: Bu modda hicbir degisiklik uygulayamazsin. Kullanici 'uygula', 'degistir', 'guncelle' derse "
                "onerilerin hazir oldugunu ama uygulamanin kullanicinin kendisi tarafindan yapilmasi gerektigini acikla. "
                "Uygun oldugunda @ikas ile MCP uzerinden veya uygulamadaki Oneriler paneliyle nasil ilerlenebilecegini oner."
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


def _normalize_matching_text(text: str) -> str:
    return (text or "").translate(MATCH_NORMALIZATION_TABLE).lower()


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
        # Check for apply/save intent before normal processing
        if self._product and self._history and APPLY_INTENT_PATTERN.search(user_message):
            return await self._handle_apply_intent(user_message)

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
                    guided_content = _append_operation_suggestion(
                        guided_fallback,
                        user_message=cleaned_message,
                        product=self._product,
                    )
                    assistant_msg = ChatMessage(role="assistant", content=guided_content)
                    self._history.append(assistant_msg)
                    return ChatResponse(
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
                guided_content = _append_operation_suggestion(
                    guided_fallback,
                    user_message=cleaned_message,
                    product=self._product,
                )
                assistant_msg = ChatMessage(role="assistant", content=guided_content)
                self._history.append(assistant_msg)
                return ChatResponse(
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
            return ChatResponse(
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

        if not response_text and guided_fallback:
            response_text = guided_fallback
        elif not response_text.strip() and thinking_text:
            response_text = (
                "Model nihai cevap uretmedi. Yerel model dusunce modunda takilmis olabilir; "
                "daha kisa bir istek deneyin veya Thinking Mode'u kapatin."
            )
        response_text = _append_operation_suggestion(
            response_text,
            user_message=cleaned_message,
            product=self._product,
        )

        # Guard against LLM hallucinating action confirmations
        response_text = _append_false_action_disclaimer(response_text, tool_results)

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

    async def _handle_apply_intent(self, user_message: str) -> ChatResponse:
        """Handle user intent to save chat suggestions as a pending SeoSuggestion."""
        from data import db

        user_msg = ChatMessage(role="user", content=user_message)
        self._history.append(user_msg)

        if not self._product:
            content = "Öneri kaydetmek için önce bir ürün seçmelisiniz."
            assistant_msg = ChatMessage(role="assistant", content=content)
            self._history.append(assistant_msg)
            return ChatResponse(content=content, error=True)

        # Check there's at least one assistant message with suggestions
        has_assistant = any(m.role == "assistant" for m in self._history[:-1])
        if not has_assistant:
            content = "Henüz kaydedilecek bir öneri yok. Önce bir SEO önerisi isteyin."
            assistant_msg = ChatMessage(role="assistant", content=content)
            self._history.append(assistant_msg)
            return ChatResponse(content=content, error=True)

        try:
            extracted = await self._extract_suggestions_from_chat()
        except Exception as exc:
            logger.warning("Suggestion extraction failed: %s", exc)
            content = (
                "Önerileri çıkarırken bir hata oluştu. "
                "Lütfen hangi alanı güncellemek istediğinizi tekrar belirtin."
            )
            assistant_msg = ChatMessage(role="assistant", content=content)
            self._history.append(assistant_msg)
            return ChatResponse(content=content, error=True)

        if not extracted:
            content = (
                "Sohbet geçmişinden somut bir öneri çıkaramadım. "
                "Lütfen güncellemek istediğiniz alanı (meta title, açıklama vb.) ve yeni değeri açıkça belirtin."
            )
            assistant_msg = ChatMessage(role="assistant", content=content)
            self._history.append(assistant_msg)
            return ChatResponse(content=content, error=True)

        suggestion = self._create_suggestion_from_extracted(extracted)
        if not suggestion:
            content = "Geçerli bir öneri oluşturulamadı. Lütfen tekrar deneyin."
            assistant_msg = ChatMessage(role="assistant", content=content)
            self._history.append(assistant_msg)
            return ChatResponse(content=content, error=True)

        # Save suggestion to database
        db.save_or_update_pending_suggestion(suggestion)

        # Build confirmation message
        field_labels = {
            "suggested_name": "Ürün Adı",
            "suggested_meta_title": "Meta Title",
            "suggested_meta_description": "Meta Description",
            "suggested_description": "Açıklama (TR)",
            "suggested_description_en": "Açıklama (EN)",
        }
        saved_fields: list[str] = []
        saved_values: dict[str, str] = {}
        for key, label in field_labels.items():
            value = extracted.get(key, "").strip()
            if value:
                saved_fields.append(f"- **{label}**: {value[:100]}{'...' if len(value) > 100 else ''}")
                saved_values[key] = value

        content_lines = [
            "✅ **Öneri kaydedildi!**",
            "",
            "Aşağıdaki alanlar öneri olarak kaydedildi:",
            *saved_fields,
            "",
            "**Sonraki adım:** Ürün detayındaki **Öneriler** sekmesinden bu öneriyi onaylayıp ikas'a uygulayabilirsiniz.",
        ]
        content = "\n".join(content_lines)

        assistant_msg = ChatMessage(role="assistant", content=content)
        self._history.append(assistant_msg)

        return ChatResponse(
            content=content,
            thinking="",
            tool_results=[],
            error=False,
            meta={"source": "suggestion_saved"},
            suggestion_saved={
                "product_id": self._product.id,
                "product_name": self._product.name,
                "fields": saved_values,
            },
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

    async def _extract_suggestions_from_chat(self) -> dict[str, str]:
        """Extract suggested field values from conversation history using a structured LLM call.

        Makes a focused extraction call asking the LLM to output only JSON with
        the suggested values from the conversation. Returns a dict of field→value.
        """
        # Build a condensed conversation for extraction
        recent_messages = self._history[-10:]  # Last 10 messages
        conversation_text = "\n".join(
            f"{'Kullanici' if m.role == 'user' else 'Asistan'}: {m.content[:500]}"
            for m in recent_messages
        )

        product_info = ""
        if self._product:
            product_info = (
                f"\nSecili urun: {self._product.name}"
                f"\nMevcut meta title: {self._product.meta_title or '-'}"
                f"\nMevcut meta description: {self._product.meta_description or '-'}"
            )

        messages = [
            {"role": "system", "content": SUGGESTION_EXTRACTION_PROMPT + product_info},
            {"role": "user", "content": conversation_text},
        ]

        base_url = self._get_base_url()
        model = self._config.ai_model_name or self._get_default_model()

        request_body = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,  # Low temperature for structured extraction
            "max_tokens": 500,
        }

        timeout = (
            httpx.Timeout(120.0, connect=10.0)
            if self._config.ai_provider in ("ollama", "lm-studio")
            else httpx.Timeout(30.0, connect=10.0)
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
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

        raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        raw_content = self._remove_thinking(raw_content)

        # Try to parse JSON from the response (handle markdown code blocks)
        json_text = raw_content.strip()
        if "```" in json_text:
            # Extract JSON from code block
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", json_text, re.DOTALL)
            if match:
                json_text = match.group(1)
        # Also try to find raw JSON object
        if not json_text.startswith("{"):
            match = re.search(r"\{[^}]+\}", json_text, re.DOTALL)
            if match:
                json_text = match.group(0)

        try:
            extracted = json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse suggestion extraction JSON: %s", json_text[:200])
            return {}

        if not isinstance(extracted, dict):
            return {}

        # Filter to only non-empty values
        valid_fields = {
            "suggested_meta_title", "suggested_meta_description",
            "suggested_name", "suggested_description", "suggested_description_en",
        }
        return {
            k: str(v).strip()
            for k, v in extracted.items()
            if k in valid_fields and isinstance(v, str) and v.strip()
        }

    def _create_suggestion_from_extracted(
        self,
        extracted: dict[str, str],
    ) -> "SeoSuggestion | None":
        """Create a SeoSuggestion from extracted chat values."""
        if not self._product or not extracted:
            return None

        from core.suggestion_service import create_pending_suggestion

        suggestion = create_pending_suggestion(self._product)

        field_map = {
            "suggested_name": "name",
            "suggested_meta_title": "meta_title",
            "suggested_meta_description": "meta_desc",
            "suggested_description": "desc_tr",
            "suggested_description_en": "desc_en",
        }

        from core.suggestion_service import apply_suggestion_field

        applied_count = 0
        for extracted_key, field_name in field_map.items():
            value = extracted.get(extracted_key, "").strip()
            if value:
                apply_suggestion_field(suggestion, field_name, value)
                applied_count += 1

        return suggestion if applied_count > 0 else None

    async def close(self) -> None:
        """Close MCP connection."""
        self.cancel_active_request()
        if self._mcp:
            await self._mcp.close()
            self._mcp = None
            self._mcp_initialized = False

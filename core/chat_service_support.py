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
import inspect
import json
import logging
import re
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

# Type alias for local tool handlers registered in ToolRegistry
ToolHandler = Callable[[dict[str, Any]], Awaitable[tuple[str, "dict[str, Any] | None"]]]

import httpx

from core.agent_tools import AgentToolkit, create_chat_toolkit
from core.ikas_client import IkasClient
from core.models import AppConfig, ChatMessage, ChatResponse, Product, SeoScore, SeoSuggestion
from core.mcp_client import IkasMCPClient, MCPError
from core.prompt_store import AGENT_SYSTEM_PROMPTS_TR
from core import chat_operation_guidance as op_guidance

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

CHAT_OPTION_BUTTONS_INSTRUCTION = """SECENEK BUTON FORMATI (KRITIK — her zaman kullan):
Kullaniciya soru sordugun, onay istedigin veya alternatif sundugunda
yanitin sonuna asagidaki formatta bir JSON blogu ekle.
Bu blok chat ekraninda tiklanabilir butonlara donusur.
Kullanici butona tiklayarak secim yapar — yazarak cevap vermesine gerek kalmaz.

Format:
```json
[{"tone": "Etiket", "value": "Buton uzerinde gorunecek aciklama"}]
```

Ornekler:

1) Onay sorusu:
```json
[{"tone": "Evet", "value": "Evet, bu degisiklikleri uygula."}, {"tone": "Hayir", "value": "Hayir, simdilik bir sey yapma."}]
```

2) Yeniden yazim alternatifleri:
```json
[{"tone": "Profesyonel", "value": "Onerilen profesyonel ton icerigi..."}, {"tone": "Agresif", "value": "Onerilen agresif ton icerigi..."}, {"tone": "Minimal", "value": "Onerilen minimal ton icerigi..."}]
```

3) Sonraki adim secenekleri:
```json
[{"tone": "Meta Duzelt", "value": "Meta title ve description'i iyilestir."}, {"tone": "Aciklama Yaz", "value": "Urun aciklamasini yeniden yaz."}, {"tone": "Hepsini Analiz Et", "value": "Tum SEO alanlarini analiz et."}]
```

Kurallar:
- Her yanit sonunda en az bir secenek blogu sun
- Yeniden yazim istenirse 2 veya 3 alternatif sun, her birinin tonunu belirt
- Onay gerektiren sorularda "Evet"/"Hayir" secenekleri sun
- JSON blogunun disinda da Markdown ile aciklamani yaz
- JSON blogu SADECE yanitinin en sonunda olsun
- SOMUT SEO DEGER ONERISI VERIRKEN (meta title, meta description, urun adi, aciklama gibi) bu degerleri ASLA duz metin/madde olarak yazma; her zaman kart formatinda (```json blogu) sun.
  Ornegin "Meta Title: ..." seklinde yazmak YASAK. Bunun yerine:
```json
[{"tone": "Meta Title", "value": "Onerilen meta title metni burada"}, {"tone": "Meta Desc", "value": "Onerilen meta description metni burada"}, {"tone": "Urun Adi", "value": "Onerilen urun adi burada"}]
```
  Bu sayede kullanici degerleri kart olarak gorur ve tek tikla secebilir.
"""

CHAT_FLOW_SYSTEM_PROMPT_TR = """Sen bir ikas e-ticaret magazasi SEO asistansin.
Sen kullanicinin SEO danismani ve icra asistanisin. Kullanici teknik detaylarla ugrasmaz; sen arka planda gerekli islemleri halledersin.

Ana gorevin:
- Konusmayi secili urun etrafinda tut
- Varsayilan olarak yalnizca mevcut SEO metrikleri, issue/suggestion alanlari ve promptta zaten bulunan urun bilgileri uzerinden tavsiye ver
- Kullanici urun aciklamasi, meta title, meta description, kategori, etiket, SKU gibi eldeki alanlari yorumlamani isterse bunu local baglamla yap
- Canli veri gerektiginde araclardan arka planda yararlan
- Somut, uygulanabilir ve kisa yanit ver
- Kullaniciyi urun bilgilerini duzeltmeye ve iyilestirmeye yonlendir

KRITIK DÜRÜSTLÜK KURALLARI (ASLA IHLAL ETME):
- ASLA yapmedigin bir islemi yaptigini iddia etme
- Bir arac cagirmadan "guncelledim", "uyguladim", "degistirdim" DEME
- Kullanici degisiklikleri onayladiginda arka planda uygun araclari cagir
- Arac basarili sonuc dondurdugunde sonucu raporla; basarisiz olursa hatanin nedenini acikla
- Emin olmadigin bilgiyi uydurma; bilmiyorsan "bilmiyorum" de

ARAC KULLANIMI (KULLANICIYA ARAC ADLARINI GOSTERME):
- Araclari arka planda sen kullanirsin; kullaniciya arac adi, API, MCP, GraphQL gibi teknik detaylari acma
- Kullanici onay verdiginde degisiklikleri otomatik uygula
- Taslak kaydetmek icin uygun araci arka planda cagir
- Skorlama, dogrulama ve urun detayi icin gerekli araclari sessizce kullan

Kurallar:
- Turkce yanit ver; kullanici Ingilizce yazarsa Ingilizce yanit ver
- Secili urunun promptta zaten bulunan statik SEO bilgileri icin yeniden arac cagirisi yapma
- SEO onerilerini mevcut skor kirilimlari, sorunlar ve gorunen urun alanlariyla sinirli tut
- Stok, fiyat, kampanya, siparis, musteri, kargo veya operasyonel konulara kullanici acikca istemedikce kendiliginden gecme
- Veri eksigi veya belirsizlik varsa acikca soyle
- Uretim tonu net, profesyonel ve kisa olsun
- Markdown kullanabilirsin
- Genis markdown tablolar yerine kisa listeler kullan; tabloyu yalnizca kullanici isterse kullan
- ASLA kullaniciya "@ikas", "@local", "MCP", "GraphQL", arac adi veya komut yazmasi gerektigini soyleme
- ASLA kullaniciya teknik arac cagirisi veya API detayi gosterme

Yaniti mumkunse su duzende kur:
1. Durum (mevcut durumu ozetle)
2. Oneri (somut iyilestirme onerileri sun)
3. Sonraki adim — asagidaki SECENEK BUTON FORMATI ile kullaniciya tiklanabilir secenekler sun

SECENEK BUTON FORMATI (KRITIK — her zaman kullan):
Kullaniciya soru sordugun, onay istedigin veya alternatif sundugunda
yanitin sonuna asagidaki formatta bir JSON blogu ekle.
Bu blok chat ekraninda tiklanabilir butonlara donusur.
Kullanici butona tiklayarak secim yapar — yazarak cevap vermesine gerek kalmaz.

Format:
```json
[{"tone": "Etiket", "value": "Buton uzerinde gorunecek aciklama"}]
```

Ornekler:

1) Onay sorusu:
```json
[{"tone": "Evet", "value": "Evet, bu degisiklikleri uygula."}, {"tone": "Hayir", "value": "Hayir, simdilik bir sey yapma."}]
```

2) Yeniden yazim alternatifleri:
```json
[{"tone": "Profesyonel", "value": "Onerilen profesyonel ton icerigi..."}, {"tone": "Agresif", "value": "Onerilen agresif ton icerigi..."}, {"tone": "Minimal", "value": "Onerilen minimal ton icerigi..."}]
```

3) Sonraki adim secenekleri:
```json
[{"tone": "Meta Duzelt", "value": "Meta title ve description'i iyilestir."}, {"tone": "Aciklama Yaz", "value": "Urun aciklamasini yeniden yaz."}, {"tone": "Hepsini Analiz Et", "value": "Tum SEO alanlarini analiz et."}]
```

Kurallar:
- Her yanit sonunda en az bir secenek blogu sun
- Yeniden yazim istenirse 2 veya 3 alternatif sun, her birinin tonunu belirt
- Onay gerektiren sorularda "Evet"/"Hayir" secenekleri sun
- JSON blogunun disinda da Markdown ile aciklamani yaz
- JSON blogu SADECE yanitinin en sonunda olsun

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
- Ozet Lensler: SEO {seo_score}/100 | GEO {geo_score}/100 | AEO {aeo_score}/100
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
Davranis kurallari:
- Urun alanlarini (name, description, meta_title, meta_description) guncelleyebilirsin. Kullanici onay verdiginde arka planda uygun araci cagir.
- Bir arac cagirmadan "guncelledim" veya "uyguladim" DEME. Bu kullaniciyi yaniltir.
- Yalnizca arac GERCEKTEN cagirilip basarili sonuc dondugunde islemi raporla.
- Kullanici degisiklik uygulamak istediginde:
  * Once degisiklikleri listele ve onay iste
  * Onaydan sonra arka planda uygun araci cagir
  * Sonucu kontrol et ve basarili/basarisiz durumu raporla
- Canli magaza verisi gerektiginde arka planda uygun sorgu araclarini kullan.
- Bu chat ekraninda varsayilan tavsiyeleri yalnizca mevcut SEO metrikleri ve secili urunun eldeki alanlariyla sinirla.
- Mutation gerektiren adimlarda kullanicidan net onay iste.
- Yanitin sonunda konusmayi ilerletecek tek bir sonraki adim veya soru oner.
- ASLA gerceklestirmedigin bir islemi basariliymiş gibi raporlama.
- ASLA kullaniciya arac adi, MCP, GraphQL, API gibi teknik detaylari gosterme.
- Kullaniciya teknik komutlar onerme; bunun yerine dogal dilde onay iste ve tiklanabilir secenekler sun.
"""

CHAT_SYSTEM_PROMPT_TR = """Sen bir ikas e-ticaret mağazası asistanısın. Mağaza sahibine ürünleri,
SEO optimizasyonu, stok durumu ve mağaza yönetimi konularında yardım ediyorsun.

Kurallar:
- Türkçe yanıt ver (kullanıcı İngilizce yazarsa İngilizce yanıt ver)
- Kısa ve öz yanıtlar ver, gereksiz uzatma
- Ürün verisi gerektiğinde sana sağlanan araçları arka planda kullan
- SEO önerilerinde somut ve uygulanabilir tavsiyeler ver
- Fiyat, stok ve sipariş bilgilerini doğru aktar
- Markdown formatında yanıt ver (başlıklar, listeler, kalın metin)
- ASLA yapmadığın bir işlemi yaptığını iddia etme
- Degisiklik uygulamak icin arka planda uygun araclari kullan; basarili oldugunda raporla
- Degisiklik uygulamadan once kullaniciya degisiklikleri goster ve onay iste
- Kullaniciya arac adi, MCP, GraphQL, API gibi teknik detaylari GOSTERME
- Kullaniciya teknik komutlar onerme; dogal dilde onay iste ve tiklanabilir secenekler sun

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
SEMANTIC_ROUTING_SYSTEM_PROMPT = (
    "Sen bir niyet tespit (intent detection) asistanisin. "
    "Kullanicinin mesajini 3 ajandan birine yonlendir: seo, operator veya general. "
    "Eger mesaj stok, fiyat, siparis, musteri, varyant veya canli magaza verisi gerektiriyorsa operator. "
    "Eger mesaj SEO, metin yazarligi, icerik onerisi veya yeniden yazim ise seo. "
    "Diger durumlarda general don. "
    'SADECE ASAGIDAKI GIBI GECERLI BIR JSON DON: {"agent_type": "seo"|"operator"|"general"}'
)
SEMANTIC_ROUTING_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

# Patterns that detect when the LLM falsely claims to have performed actions.
# These are matched against normalized (ASCII-like) text.
FALSE_ACTION_CLAIM_NORMALIZED_PATTERN = re.compile(
    r"\b(?:"
    r"uygula(?:n)?d(?:im|i)?|"
    r"guncelle(?:n)?d(?:im|i)?|"
    r"degistir(?:di|dim)?|"
    r"kaydet(?:ti|tim)?|"
    r"ekle(?:di|dim)?|"
    r"yaz(?:di|dim)?|"
    r"duzenle(?:di|dim)?|"
    r"applied|updated|saved|changed|modified"
    r")\b",
    re.IGNORECASE,
)
FALSE_ACTION_CONFIRMATION_NORMALIZED_PATTERN = re.compile(
    r"(?:"
    r"uygulama sonrasi|"
    r"basariyla (?:uygula|guncelle|kaydet)|"
    r"iyilestirilmis skor|"
    r"yeni seo (?:skoru|durumu)|"
    r"yapilan degisiklikler|"
    r"guncellemeler uygulandi|"
    r"successfully (?:applied|updated|saved)"
    r")",
    re.IGNORECASE,
)

FALSE_ACTION_DISCLAIMER_TR = (
    "\n\n---\n"
    "⚠️ **Not:** Yukarıdaki öneriler henüz uygulanmadı. "
    "Degisiklikleri uygulamak icin:\n"
    "- 'Uygula' veya 'onayla' diyerek onay verin,\n"
    "- Sohbetteki secenek kartlarindan birini secin."
)

SAVE_SEO_SUGGESTION_TOOL_NAME = "save_seo_suggestion"
SUGGESTION_SAVE_SUCCESS_MESSAGE = "\u00d6neri ba\u015far\u0131yla kaydedildi"
SAVE_SEO_SUGGESTION_TOOL_INSTRUCTION = (
    "Kullanici sohbet sirasinda sunulan SEO degisikliklerini onaylayip "
    "'uygula', 'kaydet', 'evet' veya 'bunu sectim' dediginde "
    "arka planda SEO oneri kaydetme aracini cagir. Bu arac degisiklikleri "
    "aninda uygulamaz; sadece bu chat oturumunda bekleyen taslak olarak tutar. "
    "Kullaniciya arac adini, teknik detaylari veya operasyon rehberini GOSTERME; "
    "onay aldiktan sonra sessizce cagir."
)
APPLY_INTENT_EXTRACTION_SYSTEM_PROMPT = (
    "Sen bir SEO suggestion extraction asistansisin. Gorevin, sadece sohbet gecmisindeki "
    "acik ve uygulanabilir SEO degisikliklerini secili urun icin `save_seo_suggestion` "
    "aracina donusturmektir. Asla yeni icerik uydurma. Sadece gecmiste net olarak gecen "
    "nihai degerleri kaydet. Kullanici kapsam daralttiysa (orn: sadece meta title), sadece o alanlari kaydet. "
    "Desteklenen alanlar: suggested_name, suggested_meta_title, suggested_meta_description, "
    "suggested_description, suggested_description_en. Kaydedilecek net bir deger yoksa tool cagirma ve "
    "yalnizca `NO_SUGGESTION_FOUND` yaz."
)
STRUCTURED_SUGGESTION_OPTIONS_INSTRUCTION = (
    "Eger birden fazla secenek uretiyorsan, yanitinin sonuna "
    "```json\n"
    '[{"tone":"Agresif","value":"..."}]\n'
    "``` "
    "formatinda gizli bir blok ekle. Bu blok yalnizca gecerli bir JSON dizisi icersin."
)
SAVE_SEO_SUGGESTION_FIELD_MAP = {
    "suggested_name": ("name", "suggested_name"),
    "suggested_meta_title": ("meta_title", "suggested_meta_title"),
    "suggested_meta_description": ("meta_desc", "suggested_meta_description"),
    "suggested_description": ("desc_tr", "suggested_description"),
    "suggested_description_en": ("desc_en", "suggested_description_en"),
}
SUGGESTION_APPLY_FIELD_CONFIG: dict[str, dict[str, str]] = {
    "suggested_name": {
        "label": "Urun Adi",
        "original_attr": "original_name",
        "update_key": "name",
    },
    "suggested_meta_title": {
        "label": "Meta Title",
        "original_attr": "original_meta_title",
        "update_key": "meta_title",
    },
    "suggested_meta_description": {
        "label": "Meta Description",
        "original_attr": "original_meta_description",
        "update_key": "meta_description",
    },
    "suggested_description": {
        "label": "Aciklama (TR)",
        "original_attr": "original_description",
        "update_key": "description",
    },
    "suggested_description_en": {
        "label": "Aciklama (EN)",
        "original_attr": "original_description_en",
        "update_key": "description_en",
    },
}
CHAT_ACTION_PATTERN = re.compile(r"\[\[CHAT_ACTION:([a-z0-9_-]+)(?::(.+?))?\]\]", re.IGNORECASE | re.DOTALL)
APPLY_INTENT_PATTERN = re.compile(
    r"\b(uygula|uygulansin|onayla|evet uygula|evet|tamam uygula)\b",
    re.IGNORECASE,
)
SAVE_INTENT_PATTERN = re.compile(
    r"\b(kaydet|taslak olarak kaydet|pending olarak kaydet|listeye kaydet)\b",
    re.IGNORECASE,
)
NON_FINAL_SUGGESTION_VALUE_PATTERN = re.compile(
    r"\b("
    r"gerekli|ekle|eklenmeli|ekleyin|yeniden yaz(?:im)?|"
    r"civari|karakter|ozet|özet|anahtar kelime odakli|"
    r"guncelle|duzelt|iyilestir|gelistir|geliştir"
    r")\b",
    re.IGNORECASE,
)
MANUAL_APPLY_ACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(vazgec|vazgeciyorum|iptal|hayir)\b", re.IGNORECASE), "single_apply_cancel"),
    (re.compile(r"\b(sadece meta|meta alan)\b", re.IGNORECASE), "single_apply_meta"),
    (re.compile(r"\b(sadece icerik|sadece aciklama|icerik alan)\b", re.IGNORECASE), "single_apply_content"),
    (re.compile(r"\b(hepsini|tumunu|tamamini|tum alanlari|evet|tamam)\b", re.IGNORECASE), "single_apply_all"),
]
SINGLE_PRODUCT_APPLY_ACTIONS = frozenset({
    "single_apply_meta",
    "single_apply_content",
    "single_apply_meta_content",
    "single_apply_all",
    "single_apply_cancel",
    "single_apply_confirm",
    "single_apply_execute",
})


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
                    "suggested_name": {
                        "type": "string",
                        "description": "Kaydedilecek yeni urun adi onerisi.",
                    },
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


APPLY_SEO_TO_IKAS_TOOL_NAME = "apply_seo_to_ikas"

# GraphQL mutation used by the apply_seo_to_ikas tool when routing through MCP
_MCP_SAVE_PRODUCT_MUTATION = """mutation SaveProduct($input: ProductInput!) {
  saveProduct(input: $input) {
    id
    name
    description
    metaData { pageTitle description }
  }
}"""


def _build_apply_seo_to_ikas_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": APPLY_SEO_TO_IKAS_TOOL_NAME,
            "description": (
                "Onaylanan SEO degisikliklerini ikas'a uygular. "
                "Kullanici urun uzerindeki degisiklikleri onayladiginda (orn: 'uygula', 'ikas'a kaydet', 'guncelle') "
                "bu araci cagir. Alan bos ise o alan guncellenmez."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Guncellenecek urunun ID'si.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Yeni urun adi (bos birak = degistirme).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Yeni TR aciklama HTML (bos birak = degistirme).",
                    },
                    "description_en": {
                        "type": "string",
                        "description": "Yeni EN aciklama (bos birak = degistirme).",
                    },
                    "meta_title": {
                        "type": "string",
                        "description": "Yeni meta title (bos birak = degistirme).",
                    },
                    "meta_description": {
                        "type": "string",
                        "description": "Yeni meta description (bos birak = degistirme).",
                    },
                },
                "required": ["product_id"],
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


def _parse_agent_type(content: str) -> str | None:
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

    agent_type = payload.get("agent_type")
    if not isinstance(agent_type, str):
        return None

    normalized = agent_type.strip().lower()
    if normalized in {"seo", "operator", "general"}:
        return normalized
    return None


def _build_product_context(product: Product | None, score: SeoScore | None, agent_type: str = "general") -> str:
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
            seo_score=score.seo_score,
            geo_score=score.geo_score,
            aeo_score=score.aeo_score,
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

    template = AGENT_SYSTEM_PROMPTS_TR.get(agent_type, AGENT_SYSTEM_PROMPTS_TR["general"])
    base_prompt = template.format(
        product_context=product_ctx,
        score_context=score_ctx,
    )
    return (
        base_prompt
        + "\n\n"
        + CHAT_OPTION_BUTTONS_INSTRUCTION
        + "\n\n"
        + IKAS_OPERATION_GUIDE_TR
    )


def _build_tool_catalog_instruction(
    tool_summaries: list[dict[str, str]],
) -> str | None:
    if not tool_summaries:
        return None

    tool_names = [tool["name"] for tool in tool_summaries if tool.get("name")]
    instructions = [
        "MCP araci kullanacaksan yalnizca asagidaki tam tool adlarini kullan.",
        "Tool adi uydurma; listede olmayan isim kullanma.",
    ]

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


def _extract_chat_action(text: str) -> str | None:
    match = CHAT_ACTION_PATTERN.search(text or "")
    if not match:
        return None
    action = (match.group(1) or "").strip().lower()
    return action or None


def _extract_chat_action_payload(text: str) -> str | None:
    """Extract the optional JSON payload from a CHAT_ACTION directive."""
    match = CHAT_ACTION_PATTERN.search(text or "")
    if not match:
        return None
    payload = (match.group(2) or "").strip()
    return payload or None


def _message_has_apply_intent(text: str) -> bool:
    normalized_text = _normalize_matching_text(text)
    return bool(normalized_text and APPLY_INTENT_PATTERN.search(normalized_text))


def _message_has_save_intent(text: str) -> bool:
    normalized_text = _normalize_matching_text(text)
    return bool(normalized_text and SAVE_INTENT_PATTERN.search(normalized_text))


def _detect_manual_apply_action(normalized_text: str) -> str | None:
    if not normalized_text:
        return None

    for pattern, action in MANUAL_APPLY_ACTION_PATTERNS:
        if pattern.search(normalized_text):
            return action
    return None


def _looks_like_final_suggestion_value(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (value or "").strip(" `\"'"))
    if len(cleaned) < 4:
        return False
    if NON_FINAL_SUGGESTION_VALUE_PATTERN.search(cleaned):
        return False
    return True


def _decode_json_string_fragment(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return ""
    try:
        return json.loads(f'"{candidate}"')
    except Exception:
        return candidate.replace('\\"', '"').replace("\\n", "\n")


def _detect_suggestion_field_heading(line: str) -> str | None:
    normalized = _normalize_matching_text(re.sub(r"^\d+\.\s*", "", line or "").strip())
    if not normalized:
        return None
    if "meta title" in normalized:
        return "suggested_meta_title"
    if "meta description" in normalized:
        return "suggested_meta_description"
    if "ingilizce aciklama" in normalized or "english description" in normalized or "aciklama (en" in normalized:
        return "suggested_description_en"
    if "urun adi" in normalized or "urun adı" in normalized or normalized.startswith("baslik"):
        return "suggested_name"
    if "aciklama" in normalized and "meta" not in normalized:
        return "suggested_description"
    return None


def _extract_suggestion_fields_from_text(content: str) -> dict[str, str]:
    extracted: dict[str, str] = {}
    if not content.strip():
        return extracted

    json_field_patterns = {
        "suggested_name": [
            r'"suggested_name"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"product_name"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
        "suggested_meta_title": [
            r'"suggested_meta_title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"meta_title"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
        "suggested_meta_description": [
            r'"suggested_meta_description"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"meta_description"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
        "suggested_description": [
            r'"suggested_description"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"turkish"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
        "suggested_description_en": [
            r'"suggested_description_en"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"english"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
    }
    for field_name, patterns in json_field_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            candidate = _decode_json_string_fragment(match.group(1))
            if _looks_like_final_suggestion_value(candidate):
                extracted[field_name] = candidate.strip()
                break

    lines = [line.rstrip() for line in content.splitlines()]
    current_field: str | None = None

    direct_patterns: list[tuple[str, re.Pattern[str]]] = [
        ("suggested_name", re.compile(r"^(?:[-*]\s*)?(?:urun adi|urun adı|product name)\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
        ("suggested_meta_title", re.compile(r"^(?:[-*]\s*)?meta title\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
        ("suggested_meta_description", re.compile(r"^(?:[-*]\s*)?meta description\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
        ("suggested_description", re.compile(r"^(?:[-*]\s*)?(?:turkce aciklama|turkçe aciklama|aciklama \(tr\)|aciklama)\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
        ("suggested_description_en", re.compile(r"^(?:[-*]\s*)?(?:ingilizce aciklama|english description|aciklama \(en\))\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        heading_field = _detect_suggestion_field_heading(stripped)
        if heading_field and ":" not in stripped:
            current_field = heading_field
            continue

        if stripped.lower().startswith("mevcut:"):
            continue

        value_match = re.match(r"^(?:oneri|öneri|uygulanacak)\s*:\s*(.+)$", stripped, re.IGNORECASE)
        if value_match and current_field:
            candidate = value_match.group(1).strip()
            if _looks_like_final_suggestion_value(candidate):
                extracted.setdefault(current_field, candidate)
            continue

        for field_name, pattern in direct_patterns:
            direct_match = pattern.match(stripped)
            if not direct_match:
                continue
            candidate = direct_match.group(1).strip()
            if _looks_like_final_suggestion_value(candidate):
                extracted.setdefault(field_name, candidate)
            break

    return extracted


def _compact_preview_text(value: str, *, limit: int = 180) -> str:
    collapsed = re.sub(r"\s+", " ", (value or "").strip())
    if not collapsed:
        return "-"
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit - 3]}..."


def _operation_footer_already_present(text: str) -> bool:
    return op_guidance.operation_footer_already_present(text)


def _select_product_operation_suggestion(
    user_message: str,
    response_text: str,
    product: Product | None,
    agent_type: str,
) -> tuple[str, str, bool]:
    return op_guidance.select_product_operation_suggestion(
        user_message,
        response_text,
        product.name if product else None,
        agent_type,
        save_suggestion_tool_name=SAVE_SEO_SUGGESTION_TOOL_NAME,
    )


def _append_operation_suggestion(
    response_text: str,
    *,
    user_message: str,
    product: Product | None,
    agent_type: str,
) -> str:
    return op_guidance.append_operation_suggestion(
        response_text,
        user_message=user_message,
        product_name=product.name if product else None,
        agent_type=agent_type,
        save_suggestion_tool_name=SAVE_SEO_SUGGESTION_TOOL_NAME,
    )


def _has_mutation_tool_result(tool_results: list[dict[str, Any]]) -> bool:
    """Check if any tool result is from a mutation (write) operation."""
    return op_guidance.has_mutation_tool_result(tool_results)


def _append_false_action_disclaimer(
    response_text: str,
    tool_results: list[dict[str, Any]],
) -> str:
    """Append a disclaimer if the LLM claims to have applied changes but no mutation was executed."""
    return op_guidance.append_false_action_disclaimer(response_text, tool_results)


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


def _lm_studio_native_base(configured_base_url: str) -> str:
    """Return LM Studio's native API root by stripping the /v1 suffix if present."""
    base = (configured_base_url or "http://localhost:1234").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


class _LMStudioNativeUnavailable(Exception):
    """Raised when the LM Studio native /api/v1/chat endpoint returns 404/405/501."""


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


# LM Studio native event names (compat endpoint) that carry no text content
_LM_STUDIO_NON_CONTENT_EVENTS: frozenset[str] = frozenset({
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


def _apply_choice_delta(
    choice: dict[str, Any],
    visible_text_filter: "_StreamingVisibleTextFilter",
    tool_calls_by_index: dict[int, dict[str, Any]],
) -> tuple[str, str, str]:
    """Process one OpenAI-style choice delta. Mutates tool_calls_by_index.

    Returns (content_delta, finish_reason, visible_chunk).
    visible_chunk is empty when tool calls are already pending.
    """
    delta = choice.get("delta", {})
    if not isinstance(delta, dict):
        delta = {}

    raw_finish_reason = choice.get("finish_reason")
    finish_reason = raw_finish_reason if isinstance(raw_finish_reason, str) and raw_finish_reason else ""

    content_delta = _extract_stream_delta_content(delta)
    visible_chunk = ""
    if content_delta:
        visible = visible_text_filter.consume(content_delta)
        if visible and not tool_calls_by_index:
            visible_chunk = visible

    delta_tool_calls = delta.get("tool_calls")
    if isinstance(delta_tool_calls, list):
        for tc_delta in delta_tool_calls:
            if isinstance(tc_delta, dict):
                _merge_stream_tool_call(tool_calls_by_index, tc_delta)

    return content_delta, finish_reason, visible_chunk


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


class ToolRegistry:
    """Dictionary-based registry that maps local tool names to async handler functions.

    Follows the Open-Closed Principle: new local tools can be registered without
    modifying _execute_chat_tool. Handlers must be async callables with the
    signature ``async (args: dict[str, Any]) -> tuple[str, dict[str, Any] | None]``.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        """Register a new tool handler under the given name."""
        self._handlers[name] = handler

    def get(self, name: str) -> ToolHandler | None:
        """Return the handler for *name*, or None if not registered."""
        return self._handlers.get(name)

    @property
    def local_tool_names(self) -> list[str]:
        """Names of all locally registered tools."""
        return list(self._handlers.keys())



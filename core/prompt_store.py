from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

PROMPT_FILES = {
    "description_system": "description_rewrite.system.txt",
    "description_user": "description_rewrite.user.txt",
    "translation_system": "translation_en.system.txt",
    "translation_user": "translation_en.user.txt",
    "geo_rewrite_system": "geo_rewrite.system.txt",
    "geo_rewrite_user": "geo_rewrite.user.txt",
}

PROMPT_EDITOR_GROUPS = [
    (
        "Aciklama",
        (
            "description_system",
            "description_user",
        ),
    ),
    (
        "Ceviri",
        (
            "translation_system",
            "translation_user",
        ),
    ),
    (
        "GEO Yeniden Yazim",
        (
            "geo_rewrite_system",
            "geo_rewrite_user",
        ),
    ),
]

PROMPT_DEFAULTS = {
    "description_system": """Sen bir e-ticaret SEO uzmanisin. Gorevin ikas magaza urunlerinin
iceriklerini Turk kullanicilar ve Google TR icin optimize etmek.

Kurallar:
- Dogal, satis odakli Turkce kullan
- Aciklama 200-400 kelime arasi
- Ilk paragrafta ana keyword gecmeli
- Aciklama alaninda p, br, ul, ol, li, strong ve em gibi basit HTML tagleri kullanabilirsin
- Ad, meta title ve meta description alanlarinda HTML kullanma
- Abartili reklam dili kullanma
- Urunun gercek ozelliklerine sadik kal

SADECE JSON dondur, baska hicbir sey yazma.""",
    "description_user": """Urun Adi: {{name}}
Mevcut Turkce Aciklama: {{description}}
Kategori: {{category}}
Hedef Keywordler: {{keywords}}

Bu urunun Turkce aciklamasini SEO icin optimize et. 200-400 kelime, dogal satis dili.
Gerekirse p, ul, li, strong ve em gibi basit HTML tagleri kullanabilirsin.
SADECE JSON dondur:
{"suggested_description": "..."}""",
    "translation_system": """You are a professional e-commerce translator.
Translate Turkish product content into natural English.

Rules:
- Preserve meaning and factual details
- Do not invent new product features
- Do not rewrite for SEO
- Simple HTML tags are allowed in the description field when useful
- Return ONLY JSON, nothing else.""",
    "translation_user": """Urun Adi: {{name}}
Mevcut Turkce Aciklama: {{description}}
Kategori: {{category}}

Bu urunun mevcut Turkce aciklamasini Ingilizceye cevir.
Kurallar:
- Anlami koru, yeni ozellik uydurma
- Dogal ve profesyonel urun Ingilizcesi kullan
- Gerekirse p, ul, li, strong ve em gibi basit HTML tagleri kullanabilirsin
- SEO icin yeniden yazma, ceviri yap
- Yanit sadece JSON olsun

{"suggested_description_en": "..."}""",
    "geo_rewrite_system": """Sen bir GEO (Generative Engine Optimization) uzmanisın. Amacın ürün açıklamalarını ChatGPT, Perplexity ve Google AI Overviews gibi botların en iyi anlayacağı ve alıntılayacağı (cite edeceği) formata çevirmek. Kurallar: 1) Asla 'harika, en iyi' gibi pazarlama dili kullanma, tamamen objektif ve ansiklopedik ol. 2) Teknik özellikleri ve sayısal verileri mutlaka madde imleriyle yapılandır. 3) Kısa, net ve bilgi yoğun (information-dense) paragraflar kullan.

SADECE JSON dondur, baska hicbir sey yazma.""",
    "geo_rewrite_user": """Urun Adi: {{name}}
Mevcut Aciklama: {{description}}
Kategori: {{category}}
Teknik Ozellikler / Mevcut SEO Sorunlari: {{issues}}
Hedef Keywordler: {{keywords}}

Bu urunu GEO (Generative Engine Optimization) icin yeniden yaz. AI botlarinin kolayca anlayip alintilayabilecegi, objektif ve bilgi yogun bir icerik olustur.
SADECE JSON dondur:
{"suggested_description": "..."}""",
}

AGENT_SEO_EXPERT_PROMPT_TR = """Sen ikas e-ticaret altyapısı için uzman bir SEO Metin Yazarısın. Amacın ürün başlıklarını, açıklamalarını ve meta etiketlerini satış odaklı ve yaratıcı bir dille optimize etmektir. Teknik mağaza verileriyle (stok, sipariş) ilgilenmezsin. Yanıtların yaratıcı, ikna edici ve SEO kurallarına (keyword yoğunluğu vb.) %100 uygun olmalıdır.

Kurallar:
- Turkce yanit ver; kullanici Ingilizce yazarsa Ingilizce yanit ver.
- Somut, uygulanabilir ve kisa SEO onerileri sun.
- Yeniden yazim istendiginde 2 veya 3 alternatif ver.
- Asla uydurma veri verme; yalnizca verilen urun/SEO baglamini kullan.

{product_context}
{score_context}"""

AGENT_STORE_OPERATOR_PROMPT_TR = """Sen ikas e-ticaret altyapısı için Veri ve Operasyon Analistisin. Amacın mağazanın canlı verilerini (stok durumları, fiyatlar, siparişler, müşteri verileri) MCP araçlarını kullanarak çekmek ve kullanıcıya net, analitik, tablo/liste formatında sunmaktır. Kesinlikle yorum katma, sadece elindeki veriyi analiz et.

Kurallar:
- Turkce yanit ver; kullanici Ingilizce yazarsa Ingilizce yanit ver.
- Canli veri gereken sorularda MCP araclarini kullan.
- Veri yoksa veya araca erisemezsen bunu acikca belirt.
- Yorum/deger yargisi katma; sadece olgusal analiz yap.

{product_context}
{score_context}"""

AGENT_GENERAL_PROMPT_TR = """Sen bir ikas e-ticaret mağazası asistanısın. Mağaza sahibine ürünleri,
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
- Degisiklik uygulamak icin kullaniciyi chat uzerindeki onay akisiyla yonlendir; once degisiklikleri goster, sonra onay al.

{product_context}
{score_context}"""

AGENT_SYSTEM_PROMPTS_TR: dict[str, str] = {
    "seo": AGENT_SEO_EXPERT_PROMPT_TR,
    "operator": AGENT_STORE_OPERATOR_PROMPT_TR,
    "general": AGENT_GENERAL_PROMPT_TR,
}

PROMPT_EDITOR_META = {
    "description_system": {
        "title": "Aciklama System Prompt",
        "description": "Turkce aciklama rewrite gorevinin genel rol ve kurallarini belirler.",
        "variables": (),
        "height": 120,
    },
    "description_user": {
        "title": "Aciklama User Prompt",
        "description": "Mevcut urun verisini kullanarak TR aciklama uretir.",
        "variables": ("name", "description", "category", "keywords"),
        "height": 170,
    },
    "translation_system": {
        "title": "Ceviri System Prompt",
        "description": "TR > EN ceviri gorevinin rol ve ceviri kurallarini belirler.",
        "variables": (),
        "height": 120,
    },
    "translation_user": {
        "title": "Ceviri User Prompt",
        "description": "Mevcut Turkce aciklamadan Ingilizce aciklama uretir.",
        "variables": ("name", "description", "category"),
        "height": 170,
    },
    "geo_rewrite_system": {
        "title": "GEO System Prompt",
        "description": "GEO yeniden yazim gorevinin rol ve kurallarini belirler.",
        "variables": (),
        "height": 120,
    },
    "geo_rewrite_user": {
        "title": "GEO User Prompt",
        "description": "Urunu AI botlari icin optimize edilmis GEO formatinda yeniden yazar.",
        "variables": ("name", "description", "category", "issues", "keywords"),
        "height": 170,
    },
}

README_TEXT = """Bu klasordeki prompt dosyalari uygulama tarafindan her AI isteginde yeniden okunur.

Ozellestirebilecegin dosyalar:
- description_rewrite.system.txt
- description_rewrite.user.txt
- translation_en.system.txt
- translation_en.user.txt

Kullanilabilir degiskenler:
- description_rewrite.user.txt: {{name}}, {{description}}, {{category}}, {{keywords}}
- translation_en.user.txt: {{name}}, {{description}}, {{category}}

Notlar:
- JSON orneklerini normal sekilde yazabilirsin. Cift kacis gerekmiyor.
- Degiskenler icin sadece {{degisken_adi}} formatini kullan.
- {{description}} alani prompt'a gonderilmeden once HTML taglerinden temizlenir.
- Dosya bos birakilirsa uygulama varsayilan prompta geri doner.
"""

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def ensure_prompt_files() -> Path:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    for key, filename in PROMPT_FILES.items():
        path = PROMPTS_DIR / filename
        if not path.exists():
            path.write_text(PROMPT_DEFAULTS[key], encoding="utf-8")

    readme_path = PROMPTS_DIR / "README.txt"
    if not readme_path.exists():
        readme_path.write_text(README_TEXT, encoding="utf-8")

    return PROMPTS_DIR


def get_prompts_dir() -> Path:
    return ensure_prompt_files()


def get_prompt_editor_groups() -> list[tuple[str, tuple[str, ...]]]:
    return list(PROMPT_EDITOR_GROUPS)


def get_prompt_editor_meta(key: str) -> dict[str, object]:
    if key not in PROMPT_EDITOR_META:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")
    return dict(PROMPT_EDITOR_META[key])


def load_prompt_template(key: str) -> str:
    if key not in PROMPT_FILES:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")

    ensure_prompt_files()
    path = PROMPTS_DIR / PROMPT_FILES[key]

    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("Prompt dosyasi okunamadi, varsayilan kullaniliyor: %s (%s)", path, exc)
        return PROMPT_DEFAULTS[key]

    return content or PROMPT_DEFAULTS[key]


def validate_prompt_template(key: str, template: str) -> None:
    if key not in PROMPT_FILES:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")

    allowed = set(PROMPT_EDITOR_META.get(key, {}).get("variables", ()))
    placeholders = set(_PLACEHOLDER_RE.findall(template))
    unknown = sorted(name for name in placeholders if name not in allowed)
    if unknown:
        unknown_text = ", ".join(unknown)
        raise ValueError(f"Bu promptta kullanilamayan degiskenler var: {unknown_text}")


def save_prompt_template(key: str, content: str) -> Path:
    if key not in PROMPT_FILES:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")

    validate_prompt_template(key, content)
    ensure_prompt_files()
    normalized = content.replace("\r\n", "\n").strip()
    path = PROMPTS_DIR / PROMPT_FILES[key]
    path.write_text(normalized, encoding="utf-8")
    return path


def reset_prompt_template(key: str) -> Path:
    if key not in PROMPT_FILES:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")

    ensure_prompt_files()
    path = PROMPTS_DIR / PROMPT_FILES[key]
    path.write_text(PROMPT_DEFAULTS[key], encoding="utf-8")
    return path


def render_prompt_template(template: str, context: dict[str, object]) -> str:
    placeholders = set(_PLACEHOLDER_RE.findall(template))
    unknown = sorted(name for name in placeholders if name not in context)
    if unknown:
        unknown_text = ", ".join(unknown)
        raise ValueError(f"Prompt dosyasi bilinmeyen degiskenler iceriyor: {unknown_text}")

    return _PLACEHOLDER_RE.sub(lambda match: str(context[match.group(1)]), template)

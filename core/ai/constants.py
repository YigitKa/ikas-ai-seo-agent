"""Prompt templates, default models, and configuration constants for AI providers."""

# ── System prompts ───────────────────────────────────────────────────────

SYSTEM_PROMPT_TR = """Sen bir e-ticaret SEO uzmanisin. Gorevin ikas magaza urunlerinin
 iceriklerini Turk kullanicilar ve Google TR icin optimize etmek.

Kurallar:
- Dogal, satis odakli Turkce kullan
- Aciklama 200-400 kelime arasi
- Ilk paragrafta ana keyword gecmeli
- Meta title max 60 karakter, marka adiyla bitir
- Meta description max 155 karakter, CTA icermeli
- Aciklama alanlarinda p, br, ul, ol, li, strong ve em gibi basit HTML tagleri kullanabilirsin
- Ad, meta title ve meta description alanlarinda HTML kullanma
- Abartili reklam dili kullanma
- Urunun gercek ozelliklerine sadik kal

SADECE JSON dondur, baska hicbir sey yazma."""

SYSTEM_PROMPT_EN = """You are an e-commerce SEO specialist. Your task is to optimize
product content for search engines and users.

Rules:
- Use natural, sales-oriented language
- Description should be 200-400 words
- Main keyword should appear in the first paragraph
- Meta title max 60 characters, end with brand name
- Meta description max 155 characters, include CTA
- You may use simple HTML tags in description fields, such as <p>, <br>, <ul>, <ol>, <li>, <strong>, and <em>
- Do not use HTML in the name, meta title, or meta description fields
- No exaggerated advertising language
- Stay faithful to the product's real features

Return ONLY JSON, nothing else."""

# ── User prompt templates ────────────────────────────────────────────────

USER_PROMPT_TEMPLATE = """Urun Adi: {name}
Mevcut Turkce Aciklama: {description}
Mevcut Ingilizce Aciklama: {description_en}
Kategori: {category}
Mevcut SEO Sorunlari: {issues}
Hedef Keywordler: {keywords}

Su alanlari optimize et ve JSON olarak dondur:
{{
    "suggested_name": "...",
    "suggested_description": "...",
    "suggested_description_en": "...",
    "suggested_meta_title": "...",
    "suggested_meta_description": "..."
}}"""

# Per-field prompt templates – smaller context, single field output
FIELD_PROMPT_TEMPLATES = {
    "name": """Urun Adi: {name}
Kategori: {category}
Hedef Keywordler: {keywords}

Bu urunun adini SEO icin optimize et. Dogal ve aranabilir bir isim olustur.
SADECE JSON dondur:
{{"suggested_name": "..."}}""",

    "meta_title": """Urun Adi: {name}
Kategori: {category}
Hedef Keywordler: {keywords}

Bu urun icin SEO uyumlu meta title yaz. Max 60 karakter, marka adiyla bitir.
SADECE JSON dondur:
{{"suggested_meta_title": "..."}}""",

    "meta_desc": """Urun Adi: {name}
Mevcut Aciklama: {description_short}
Hedef Keywordler: {keywords}

Bu urun icin SEO uyumlu meta description yaz. Max 155 karakter, CTA icermeli.
SADECE JSON dondur:
{{"suggested_meta_description": "..."}}""",

    "desc_en": """Urun Adi: {name}
Mevcut Ingilizce Aciklama: {description_en}
Kategori: {category}
Hedef Keywordler: {keywords}

Rewrite the English product description for SEO. 200-400 words, natural sales language.
Simple HTML is allowed in the description field when useful.
Return ONLY JSON:
{{"suggested_description_en": "..."}}""",
}

# ── Provider configuration ───────────────────────────────────────────────

# Default models per provider
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.2",
    "lm-studio": "local-model",
    "custom": "gpt-3.5-turbo",
}

# OpenAI-compatible base URLs
PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "lm-studio": "http://localhost:1234/v1",
}

# ── Field mappings ───────────────────────────────────────────────────────

# Mapping from field key to the JSON key in the response
FIELD_RESULT_KEYS = {
    "name": "suggested_name",
    "meta_title": "suggested_meta_title",
    "meta_desc": "suggested_meta_description",
    "desc_tr": "suggested_description",
    "desc_en": "suggested_description_en",
}

FIELD_MAX_OUTPUT_TOKENS = {
    "name": 96,
    "meta_title": 96,
    "meta_desc": 192,
    "desc_tr": 1024,
    "desc_en": 1024,
}

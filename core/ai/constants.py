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
    "desc_en": 2048,
}

# ── Model pricing (USD per 1M tokens) ───────────────────────────────────
# Keys are substrings matched against the model name (case-insensitive).
# Order matters: first match wins. More specific patterns should come first.

MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic Claude — (input_per_1M, output_per_1M)
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4": (30.0, 60.0),
    "gpt-3.5": (0.50, 1.50),
    "o3-mini": (1.10, 4.40),
    "o3": (10.0, 40.0),
    "o1-mini": (3.0, 12.0),
    "o1": (15.0, 60.0),
    # Google Gemini
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost based on model name and token counts.

    Returns 0.0 if the model is not recognized.
    """
    model_lower = model.lower()
    for pattern, (inp_price, out_price) in MODEL_PRICING.items():
        if pattern in model_lower:
            return round(
                input_tokens * inp_price / 1_000_000
                + output_tokens * out_price / 1_000_000,
                6,
            )
    return 0.0

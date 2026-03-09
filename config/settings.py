import json
import os
import sys
from getpass import getpass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from core.models import AppConfig

load_dotenv()

_config: Optional[AppConfig] = None
USER_SETTINGS_PATH = Path(".cache/user_settings.json")


REQUIRED_ENV_VARS = {
    "IKAS_STORE_NAME": "ikas magaza alt alani (ornek: my-store)",
    "IKAS_CLIENT_ID": "ikas OAuth2 Client ID",
    "IKAS_CLIENT_SECRET": "ikas OAuth2 Client Secret",
}

PROMPT_ONLY_ENV_VARS = {
    "ANTHROPIC_API_KEY": "legacy Anthropic API key (opsiyonel, geriye donuk uyumluluk)",
}

# Mapping: settings-dict key → canonical env-style key name
KEY_MAP = {
    "store_name": "IKAS_STORE_NAME",
    "client_id": "IKAS_CLIENT_ID",
    "client_secret": "IKAS_CLIENT_SECRET",
    "mcp_token": "IKAS_MCP_TOKEN",
    "ai_provider": "AI_PROVIDER",
    "ai_api_key": "AI_API_KEY",
    "ai_base_url": "AI_BASE_URL",
    "ai_model_name": "AI_MODEL_NAME",
    "ai_temperature": "AI_TEMPERATURE",
    "ai_max_tokens": "AI_MAX_TOKENS",
    "ai_thinking_mode": "AI_THINKING_MODE",
    "languages": "STORE_LANGUAGES",
    "keywords": "SEO_TARGET_KEYWORDS",
    "dry_run": "DRY_RUN",
}


def _get_user_overrides() -> dict[str, str]:
    """Read persisted runtime settings from local JSON (fallback-safe)."""
    try:
        if not USER_SETTINGS_PATH.exists():
            return {}
        with USER_SETTINGS_PATH.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}


def _getenv(key: str, overrides: dict[str, str], default: str = "") -> str:
    """Return the value for *key*, preferring user overrides over environment."""
    return overrides.get(key) or os.getenv(key, default)


def _prompt_for_missing_env_vars(overrides: dict[str, str]) -> None:
    missing_required = [key for key in REQUIRED_ENV_VARS if not _getenv(key, overrides).strip()]
    missing_prompt_only = [key for key in PROMPT_ONLY_ENV_VARS if not _getenv(key, overrides).strip()]
    missing = missing_required + missing_prompt_only
    if not missing:
        return

    if not sys.stdin.isatty():
        if not missing_required:
            return
        missing_text = ", ".join(missing_required)
        raise ValueError(
            f"Eksik zorunlu ortam degiskenleri: {missing_text}. "
            "Lutfen .env dosyasini doldurun veya interaktif terminalde uygulamayi calistirin.",
        )

    print("\n[Config] Bazi zorunlu ayarlar eksik. Devam etmek icin degerleri girin:")
    for key in missing:
        desc = REQUIRED_ENV_VARS.get(key) or PROMPT_ONLY_ENV_VARS[key]
        while True:
            prompt_text = f"{key} ({desc}): "
            value = getpass(prompt_text) if "SECRET" in key or "KEY" in key else input(prompt_text)
            value = value.strip()
            if value:
                os.environ[key] = value
                break
            print(f"{key} bos birakilamaz.")


def _parse_bool(raw: Optional[str], default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return _parse_bool(raw, default)


def _parse_store_languages(raw: str = "") -> list[str]:
    if not raw:
        raw = os.getenv("STORE_LANGUAGES", "").strip()
    if not raw:
        raw = os.getenv("STORE_LANGUAGE", "tr")
    languages = [lang.strip().lower() for lang in raw.split(",") if lang.strip()]
    return languages or ["tr"]


def _detect_default_provider(overrides: dict[str, str]) -> str:
    """Auto-detect provider from user overrides / legacy env vars."""
    val = _getenv("AI_PROVIDER", overrides).strip()
    if val:
        return val.lower()
    if _getenv("ANTHROPIC_API_KEY", overrides).strip():
        return "anthropic"
    return "none"


def _parse_float(raw: Optional[str], default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _parse_int(raw: Optional[str], default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _parse_float_env(name: str, default: float) -> float:
    return _parse_float(os.getenv(name), default)


def _parse_int_env(name: str, default: int) -> int:
    return _parse_int(os.getenv(name), default)


def get_config() -> AppConfig:
    global _config
    if _config is not None:
        return _config

    # User runtime settings override .env values.
    overrides = _get_user_overrides()

    _prompt_for_missing_env_vars(overrides)

    keywords_raw = _getenv("SEO_TARGET_KEYWORDS", overrides, "")
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    store_name = _getenv("IKAS_STORE_NAME", overrides, "")
    languages_raw = _getenv("STORE_LANGUAGES", overrides, "") or _getenv("STORE_LANGUAGE", overrides, "")
    store_languages = _parse_store_languages(languages_raw)

    provider = _detect_default_provider(overrides)
    ai_api_key = (
        _getenv("AI_API_KEY", overrides, "")
        or _getenv("ANTHROPIC_API_KEY", overrides, "")
    )

    _config = AppConfig(
        ikas_store_name=store_name,
        ikas_client_id=_getenv("IKAS_CLIENT_ID", overrides, ""),
        ikas_client_secret=_getenv("IKAS_CLIENT_SECRET", overrides, ""),
        ikas_api_url="https://api.myikas.com/api/v1/admin/graphql",
        ikas_mcp_token=_getenv("IKAS_MCP_TOKEN", overrides, ""),
        anthropic_api_key=_getenv("ANTHROPIC_API_KEY", overrides, ""),
        store_language=store_languages[0],
        store_languages=store_languages,
        seo_target_keywords=keywords,
        dry_run=_parse_bool(_getenv("DRY_RUN", overrides) or None, default=True),
        log_level=_getenv("LOG_LEVEL", overrides, "INFO"),
        ai_provider=provider,
        ai_api_key=ai_api_key,
        ai_base_url=_getenv("AI_BASE_URL", overrides, ""),
        ai_model_name=_getenv("AI_MODEL_NAME", overrides, ""),
        ai_temperature=_parse_float(_getenv("AI_TEMPERATURE", overrides) or None, 0.7),
        ai_max_tokens=_parse_int(_getenv("AI_MAX_TOKENS", overrides) or None, 2000),
        ai_thinking_mode=_parse_bool(_getenv("AI_THINKING_MODE", overrides) or None, default=False),
        seo_low_score_threshold=_parse_int(_getenv("SEO_LOW_SCORE_THRESHOLD", overrides) or None, 70),
    )
    return _config


def reset_config() -> None:
    global _config
    _config = None


async def save_config_to_db(values: dict) -> None:
    """Persist settings to local JSON and reset the in-memory config cache.

    The physical .env file is NEVER modified; it remains a read-only fallback
    for default values.  This makes the application safe for read-only
    filesystems (Docker, Cloud Run, etc.).
    """
    overrides = _get_user_overrides()
    for settings_key, env_key in KEY_MAP.items():
        if settings_key in values:
            val = values[settings_key]
            if isinstance(val, bool):
                val = "true" if val else "false"
            overrides[env_key] = str(val)

    USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_SETTINGS_PATH.open("w", encoding="utf-8") as fp:
        json.dump(overrides, fp, ensure_ascii=False, indent=2)

    reset_config()


# ---------------------------------------------------------------------------
# Backward-compatibility shim — callers that still import save_config_to_env
# will automatically use the JSON-based implementation.
# ---------------------------------------------------------------------------
save_config_to_env = save_config_to_db

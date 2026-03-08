import os
import sys
from getpass import getpass
from typing import Optional

from dotenv import load_dotenv

from core.models import AppConfig

load_dotenv()

_config: Optional[AppConfig] = None


REQUIRED_ENV_VARS = {
    "IKAS_STORE_NAME": "ikas magaza alt alani (ornek: my-store)",
    "IKAS_CLIENT_ID": "ikas OAuth2 Client ID",
    "IKAS_CLIENT_SECRET": "ikas OAuth2 Client Secret",
}

PROMPT_ONLY_ENV_VARS = {
    "ANTHROPIC_API_KEY": "legacy Anthropic API key (opsiyonel, geriye donuk uyumluluk)",
}


def _prompt_for_missing_env_vars() -> None:
    missing_required = [key for key in REQUIRED_ENV_VARS if not os.getenv(key, "").strip()]
    missing_prompt_only = [key for key in PROMPT_ONLY_ENV_VARS if not os.getenv(key, "").strip()]
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


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _parse_store_languages() -> list[str]:
    # New preferred key: STORE_LANGUAGES=tr,en,de
    raw = os.getenv("STORE_LANGUAGES", "").strip()
    # Backward compatibility: STORE_LANGUAGE can now be either single or comma-separated.
    if not raw:
        raw = os.getenv("STORE_LANGUAGE", "tr")

    languages = [lang.strip().lower() for lang in raw.split(",") if lang.strip()]
    return languages or ["tr"]


def _detect_default_provider() -> str:
    """Auto-detect provider from legacy env vars for backward compatibility."""
    if os.getenv("AI_PROVIDER", "").strip():
        return os.getenv("AI_PROVIDER", "").strip().lower()
    # Backward compat: if only ANTHROPIC_API_KEY is set, default to anthropic
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return "anthropic"
    return "none"


def _parse_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def get_config() -> AppConfig:
    global _config
    if _config is not None:
        return _config

    _prompt_for_missing_env_vars()

    keywords_raw = os.getenv("SEO_TARGET_KEYWORDS", "")
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    store_name = os.getenv("IKAS_STORE_NAME", "")
    store_languages = _parse_store_languages()

    provider = _detect_default_provider()
    # ai_api_key: prefer AI_API_KEY, fall back to ANTHROPIC_API_KEY for compat
    ai_api_key = os.getenv("AI_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")

    _config = AppConfig(
        ikas_store_name=store_name,
        ikas_client_id=os.getenv("IKAS_CLIENT_ID", ""),
        ikas_client_secret=os.getenv("IKAS_CLIENT_SECRET", ""),
        ikas_api_url="https://api.myikas.com/api/v1/admin/graphql",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        store_language=store_languages[0],
        store_languages=store_languages,
        seo_target_keywords=keywords,
        dry_run=_parse_bool_env("DRY_RUN", default=True),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        ai_provider=provider,
        ai_api_key=ai_api_key,
        ai_base_url=os.getenv("AI_BASE_URL", ""),
        ai_model_name=os.getenv("AI_MODEL_NAME", ""),
        ai_temperature=_parse_float_env("AI_TEMPERATURE", 0.7),
        ai_max_tokens=_parse_int_env("AI_MAX_TOKENS", 2000),
        ai_thinking_mode=_parse_bool_env("AI_THINKING_MODE", default=False),
        seo_low_score_threshold=_parse_int_env("SEO_LOW_SCORE_THRESHOLD", 70),
    )
    return _config


def reset_config() -> None:
    global _config
    _config = None


def save_config_to_env(values: dict) -> None:
    """Persist settings dict to .env file and reset the in-memory config cache."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

    # Read existing lines
    existing: dict[str, str] = {}
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.rstrip("\n")
                if "=" in stripped and not stripped.startswith("#"):
                    key, _, val = stripped.partition("=")
                    existing[key.strip()] = val
                lines.append(stripped)

    # Mapping from settings dict keys to .env variable names
    key_map = {
        "store_name": "IKAS_STORE_NAME",
        "client_id": "IKAS_CLIENT_ID",
        "client_secret": "IKAS_CLIENT_SECRET",
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

    updates: dict[str, str] = {}
    for settings_key, env_key in key_map.items():
        if settings_key in values:
            val = values[settings_key]
            if isinstance(val, bool):
                val = "true" if val else "false"
            updates[env_key] = str(val)

    # Update or append
    written_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            key = line.partition("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                written_keys.add(key)
                continue
        new_lines.append(line)

    for env_key, val in updates.items():
        if env_key not in written_keys:
            new_lines.append(f"{env_key}={val}")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
        if new_lines and not new_lines[-1].endswith("\n"):
            f.write("\n")

    # Reload env and reset config cache
    load_dotenv(env_path, override=True)
    reset_config()

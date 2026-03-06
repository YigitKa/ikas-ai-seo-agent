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
    "ANTHROPIC_API_KEY": "Anthropic API anahtari (sk-ant-...)",
}


def _prompt_for_missing_env_vars() -> None:
    missing = [key for key in REQUIRED_ENV_VARS if not os.getenv(key, "").strip()]
    if not missing:
        return

    if not sys.stdin.isatty():
        missing_text = ", ".join(missing)
        raise ValueError(
            f"Eksik zorunlu ortam degiskenleri: {missing_text}. "
            "Lutfen .env dosyasini doldurun veya interaktif terminalde uygulamayi calistirin.",
        )

    print("\n[Config] Bazi zorunlu ayarlar eksik. Devam etmek icin degerleri girin:")
    for key in missing:
        desc = REQUIRED_ENV_VARS[key]
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


def get_config() -> AppConfig:
    global _config
    if _config is not None:
        return _config

    _prompt_for_missing_env_vars()

    keywords_raw = os.getenv("SEO_TARGET_KEYWORDS", "")
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    store_name = os.getenv("IKAS_STORE_NAME", "")
    store_languages = _parse_store_languages()

    _config = AppConfig(
        ikas_store_name=store_name,
        ikas_client_id=os.getenv("IKAS_CLIENT_ID", ""),
        ikas_client_secret=os.getenv("IKAS_CLIENT_SECRET", ""),
        ikas_api_url=f"https://{store_name}.myikas.com/api/admin/graphql" if store_name else "",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        store_language=store_languages[0],
        store_languages=store_languages,
        seo_target_keywords=keywords,
        dry_run=_parse_bool_env("DRY_RUN", default=True),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    return _config


def reset_config() -> None:
    global _config
    _config = None

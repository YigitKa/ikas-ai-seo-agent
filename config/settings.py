import os
from typing import Optional

from dotenv import load_dotenv

from core.models import AppConfig

load_dotenv()

_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config
    if _config is not None:
        return _config

    keywords_raw = os.getenv("SEO_TARGET_KEYWORDS", "")
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    store_name = os.getenv("IKAS_STORE_NAME", "")

    _config = AppConfig(
        ikas_store_name=store_name,
        ikas_client_id=os.getenv("IKAS_CLIENT_ID", ""),
        ikas_client_secret=os.getenv("IKAS_CLIENT_SECRET", ""),
        ikas_api_url=f"https://{store_name}.myikas.com/api/admin/graphql" if store_name else "",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        store_language=os.getenv("STORE_LANGUAGE", "tr"),
        seo_target_keywords=keywords,
        dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
    return _config


def reset_config() -> None:
    global _config
    _config = None

from __future__ import annotations

from typing import Any

import httpx

from core.ai_client import PROVIDER_BASE_URLS
from core.models import AppConfig

PROVIDERS = [
    "none",
    "anthropic",
    "openai",
    "gemini",
    "openrouter",
    "ollama",
    "lm-studio",
    "custom",
]

PROVIDER_LABELS = {
    "none": "None (yalnizca analiz)",
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI (GPT)",
    "gemini": "Google Gemini",
    "openrouter": "OpenRouter",
    "ollama": "Ollama (yerel)",
    "lm-studio": "LM Studio (yerel)",
    "custom": "Custom OpenAI-compatible",
}

PROVIDER_MODEL_OPTIONS = {
    "anthropic": [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5-20250514",
        "claude-opus-4-5-20250514",
        "claude-haiku-3-5-20241022",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
    "gemini": [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
    ],
    "openrouter": [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "anthropic/claude-3-haiku",
        "anthropic/claude-3-sonnet",
        "google/gemini-flash-1.5",
        "meta-llama/llama-3-8b-instruct",
    ],
}


def provider_key_from_label(label: str) -> str:
    return next((key for key, value in PROVIDER_LABELS.items() if value == label), "none")


def provider_label_from_key(provider: str) -> str:
    return PROVIDER_LABELS.get(provider, PROVIDER_LABELS["none"])


def get_provider_model_options(provider: str) -> list[str]:
    return list(PROVIDER_MODEL_OPTIONS.get(provider, ()))


def resolve_provider_base_url(provider: str, base_url: str = "") -> str:
    normalized = (base_url or PROVIDER_BASE_URLS.get(provider, "")).rstrip("/")
    if not normalized:
        return ""
    if provider in {"openai", "openrouter", "ollama", "lm-studio", "custom"} and not normalized.endswith("/v1"):
        return normalized + "/v1"
    return normalized


def _provider_headers(provider: str, api_key: str, config: AppConfig | None = None) -> dict[str, str]:
    if provider == "anthropic":
        key = api_key or (config.anthropic_api_key if config is not None else "")
        if not key:
            return {}
        return {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        }
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    return {}


def _extract_first_model_id(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return str(first.get("id") or "")
    return ""


def get_provider_health(config: AppConfig, timeout: float = 5.0) -> dict[str, str]:
    provider = config.ai_provider.lower()
    if provider == "none":
        return {"status": "disabled", "message": "\u25cf Provider yok"}

    try:
        if provider == "anthropic":
            response = httpx.get(
                "https://api.anthropic.com/v1/models",
                headers=_provider_headers(provider, config.ai_api_key, config),
                timeout=timeout,
            )
        else:
            base_url = resolve_provider_base_url(provider, config.ai_base_url)
            if not base_url:
                return {"status": "missing_url", "message": "\u25cf URL yok"}
            response = httpx.get(
                f"{base_url}/models",
                headers=_provider_headers(provider, config.ai_api_key, config),
                timeout=timeout,
            )

        if response.status_code != 200:
            return {"status": "error", "message": f"\u25cf HTTP {response.status_code}"}

        model_name = _extract_first_model_id(response.json())
        suffix = f" [{model_name}]" if model_name else ""
        return {"status": "ok", "message": f"\u25cf Bagli{suffix}"}
    except Exception:
        return {"status": "offline", "message": "\u25cf Cevrimdisi"}


def discover_provider_models(provider: str, base_url: str = "", timeout: float = 5.0) -> list[str]:
    provider = provider.lower()
    if provider == "ollama":
        ollama_base = (base_url or PROVIDER_BASE_URLS["ollama"]).rstrip("/")
        if ollama_base.endswith("/v1"):
            ollama_base = ollama_base[:-3]
        response = httpx.get(f"{ollama_base}/api/tags", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        return [str(item["name"]) for item in payload.get("models", []) if isinstance(item, dict) and item.get("name")]

    if provider == "lm-studio":
        lm_studio_base = resolve_provider_base_url(provider, base_url or PROVIDER_BASE_URLS["lm-studio"])
        response = httpx.get(f"{lm_studio_base}/models", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        return [str(item["id"]) for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")]

    raise ValueError(f"Model discovery desteklenmiyor: {provider}")


def resolve_lm_studio_native_base_url(base_url: str = "") -> str:
    base = (base_url or PROVIDER_BASE_URLS["lm-studio"]).rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


def _extract_lm_studio_model_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("data")
        items = raw_items if isinstance(raw_items, list) else []
    else:
        items = []

    return [item for item in items if isinstance(item, dict)]


def _normalize_lm_studio_model(item: dict[str, Any]) -> dict[str, Any]:
    context_length = (
        item.get("context_length")
        or item.get("max_context_length")
        or item.get("contextLength")
        or item.get("maxContextLength")
    )
    status = (
        item.get("status")
        or item.get("state")
        or ("loaded" if item.get("loaded") else "")
    )
    return {
        "id": str(item.get("id") or item.get("model_key") or item.get("name") or ""),
        "display_name": str(item.get("display_name") or item.get("name") or item.get("id") or ""),
        "status": str(status or ""),
        "context_length": int(context_length) if isinstance(context_length, (int, float)) else None,
    }


def get_lm_studio_live_status(
    config: AppConfig,
    *,
    job_id: str = "",
    timeout: float = 5.0,
) -> dict[str, Any]:
    provider = config.ai_provider.lower()
    if provider != "lm-studio":
        raise ValueError("LM Studio live status sadece lm-studio provider icin gecerlidir.")

    native_base = resolve_lm_studio_native_base_url(config.ai_base_url)
    if not native_base:
        raise ValueError("LM Studio base URL bulunamadi.")

    headers = _provider_headers(provider, config.ai_api_key, config)
    response = httpx.get(f"{native_base}/api/v1/models", headers=headers, timeout=timeout)
    response.raise_for_status()
    model_items = [
        _normalize_lm_studio_model(item)
        for item in _extract_lm_studio_model_items(response.json())
    ]

    selected_model = None
    configured_model = (config.ai_model_name or "").strip()
    if configured_model:
        selected_model = next(
            (item for item in model_items if item["id"] == configured_model or item["display_name"] == configured_model),
            None,
        )
    if selected_model is None:
        selected_model = next((item for item in model_items if item.get("status") == "loaded"), None)
    if selected_model is None and model_items:
        selected_model = model_items[0]

    download_status: dict[str, Any] | None = None
    normalized_job_id = job_id.strip()
    if normalized_job_id:
        download_response = httpx.get(
            f"{native_base}/api/v1/models/download/status/{normalized_job_id}",
            headers=headers,
            timeout=timeout,
        )
        download_response.raise_for_status()
        payload = download_response.json()
        if isinstance(payload, dict):
            download_status = {
                "job_id": str(payload.get("job_id") or normalized_job_id),
                "status": str(payload.get("status") or ""),
                "bytes_per_second": payload.get("bytes_per_second"),
                "estimated_completion": str(payload.get("estimated_completion") or ""),
                "completed_at": str(payload.get("completed_at") or ""),
                "total_size_bytes": payload.get("total_size_bytes"),
                "downloaded_bytes": payload.get("downloaded_bytes"),
                "started_at": str(payload.get("started_at") or ""),
            }

    return {
        "provider": "lm-studio",
        "configured_model": configured_model,
        "selected_model": selected_model or {},
        "models": model_items,
        "download_status": download_status,
    }


def test_settings_connection(values: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    provider = str(values.get("ai_provider") or "none").lower()
    if provider == "none":
        return {
            "ok": True,
            "ikas_ok": False,
            "message": "Provider 'none' - test gerekmiyor.",
        }

    store_name = str(values.get("store_name") or "").strip()
    client_id = str(values.get("client_id") or "").strip()
    client_secret = str(values.get("client_secret") or "").strip()
    ikas_ok = False

    if store_name and client_id and client_secret:
        response = httpx.post(
            f"https://{store_name}.myikas.com/api/admin/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=timeout,
        )
        ikas_ok = response.status_code == 200

    has_api_key = bool(str(values.get("ai_api_key") or "").strip())
    message = (
        f"ikas: {'OK' if ikas_ok else 'Hata'} | "
        f"AI provider: {provider} (anahtar girildi: {'evet' if has_api_key else 'hayir'})"
    )
    return {
        "ok": ikas_ok,
        "ikas_ok": ikas_ok,
        "message": message,
    }

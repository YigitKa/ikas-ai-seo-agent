"""Settings endpoints — read, update, test connection, provider info."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_manager
from api.schemas import (
    MessageResponse,
    ProviderHealthResponse,
    ProviderModelsResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    TestConnectionResponse,
)
from core.product_manager import ProductManager
from core.provider_service import PROVIDERS, PROVIDER_LABELS

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings(
    manager: ProductManager = Depends(get_manager),
) -> SettingsResponse:
    """Return current configuration (secrets masked)."""
    cfg = manager.get_config()
    return SettingsResponse(
        store_name=cfg.ikas_store_name,
        client_id=cfg.ikas_client_id,
        client_secret=cfg.ikas_client_secret,
        ai_provider=cfg.ai_provider,
        ai_api_key=cfg.ai_api_key,
        ai_base_url=cfg.ai_base_url,
        ai_model_name=cfg.ai_model_name,
        ai_temperature=cfg.ai_temperature,
        ai_max_tokens=cfg.ai_max_tokens,
        ai_thinking_mode=cfg.ai_thinking_mode,
        languages=",".join(cfg.store_languages),
        keywords=",".join(cfg.seo_target_keywords),
        dry_run=cfg.dry_run,
    )


@router.put("", response_model=MessageResponse)
async def update_settings(
    body: SettingsUpdateRequest,
    manager: ProductManager = Depends(get_manager),
) -> MessageResponse:
    """Persist settings to .env and reload."""
    manager.save_settings(body.values)
    return MessageResponse(message="Settings updated")


@router.get("/providers")
async def list_providers() -> dict[str, list[dict[str, str]]]:
    """Return available providers with labels."""
    return {
        "providers": [
            {"key": key, "label": PROVIDER_LABELS.get(key, key)}
            for key in PROVIDERS
        ]
    }


@router.get("/health", response_model=ProviderHealthResponse)
async def provider_health(
    manager: ProductManager = Depends(get_manager),
) -> ProviderHealthResponse:
    """Check AI provider connectivity."""
    result = manager.get_provider_health()
    return ProviderHealthResponse(status=result["status"], message=result["message"])


@router.get("/models/{provider}", response_model=ProviderModelsResponse)
async def list_models(
    provider: str,
    base_url: str = "",
    manager: ProductManager = Depends(get_manager),
) -> ProviderModelsResponse:
    """Discover available models for a provider."""
    try:
        models = manager.discover_provider_models(provider, base_url=base_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ProviderModelsResponse(models=models)


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    body: SettingsUpdateRequest,
    manager: ProductManager = Depends(get_manager),
) -> TestConnectionResponse:
    """Test ikas + AI provider connection with given settings."""
    result = manager.test_settings_connection(body.values)
    return TestConnectionResponse(
        ok=result.get("ok", False),
        ikas_ok=result.get("ikas_ok", False),
        message=result.get("message", ""),
    )

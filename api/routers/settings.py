"""Settings endpoints — read, update, test connection, provider info."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_manager
from api.schemas import (
    MessageResponse,
    LMStudioDownloadStatusResponse,
    LMStudioLiveStatusResponse,
    LMStudioModelStatusResponse,
    PromptGroupResponse,
    PromptResetRequest,
    PromptTemplateResponse,
    PromptTemplatesResponse,
    PromptTemplatesUpdateRequest,
    ProviderHealthResponse,
    ProviderModelsResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    TestConnectionResponse,
)
from core.product_manager import ProductManager
from core.provider_service import PROVIDERS, PROVIDER_LABELS
from core.settings_service import SettingsService

router = APIRouter()
settings_service = SettingsService()


def _build_prompt_templates_response() -> PromptTemplatesResponse:
    groups: list[PromptGroupResponse] = []
    for group_label, prompt_keys in settings_service.get_prompt_editor_groups():
        prompts: list[PromptTemplateResponse] = []
        for prompt_key in prompt_keys:
            meta = settings_service.get_prompt_editor_meta(prompt_key)
            prompts.append(
                PromptTemplateResponse(
                    key=prompt_key,
                    title=str(meta.get("title") or prompt_key),
                    description=str(meta.get("description") or ""),
                    variables=[str(name) for name in meta.get("variables", ())],
                    height=int(meta.get("height", 150)),
                    content=settings_service.load_prompt_template(prompt_key),
                )
            )
        groups.append(PromptGroupResponse(label=group_label, prompts=prompts))
    return PromptTemplatesResponse(groups=groups)


def _raise_prompt_http_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))


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
        mcp_token=cfg.ikas_mcp_token,
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


@router.get("/prompts", response_model=PromptTemplatesResponse)
async def get_prompt_templates() -> PromptTemplatesResponse:
    """Return editable prompt templates with metadata."""
    return _build_prompt_templates_response()


@router.put("/prompts", response_model=MessageResponse)
async def update_prompt_templates(
    body: PromptTemplatesUpdateRequest,
) -> MessageResponse:
    """Persist prompt template updates."""
    try:
        settings_service.save_prompt_templates(body.templates)
    except Exception as exc:
        _raise_prompt_http_error(exc)
    return MessageResponse(message="Prompt templates updated")


@router.post("/prompts/reset", response_model=PromptTemplatesResponse)
async def reset_prompt_templates(
    body: PromptResetRequest,
) -> PromptTemplatesResponse:
    """Reset selected prompt templates or all templates to defaults."""
    try:
        prompt_keys = list(body.prompt_keys)
        if not prompt_keys:
            prompt_keys = [
                prompt.key
                for group in _build_prompt_templates_response().groups
                for prompt in group.prompts
            ]
        settings_service.reset_prompt_templates(prompt_keys)
    except Exception as exc:
        _raise_prompt_http_error(exc)
    return _build_prompt_templates_response()


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


@router.get("/lm-studio/status", response_model=LMStudioLiveStatusResponse)
async def lm_studio_live_status(
    job_id: str = "",
    manager: ProductManager = Depends(get_manager),
) -> LMStudioLiveStatusResponse:
    """Return live LM Studio model/context status and optional download job progress."""
    try:
        result = manager.get_lm_studio_live_status(job_id=job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    selected_model = LMStudioModelStatusResponse(**result.get("selected_model", {}))
    models = [LMStudioModelStatusResponse(**item) for item in result.get("models", [])]
    download_payload = result.get("download_status")
    download_status = (
        LMStudioDownloadStatusResponse(**download_payload)
        if isinstance(download_payload, dict)
        else None
    )
    return LMStudioLiveStatusResponse(
        provider=str(result.get("provider") or "lm-studio"),
        configured_model=str(result.get("configured_model") or ""),
        selected_model=selected_model,
        models=models,
        download_status=download_status,
    )


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

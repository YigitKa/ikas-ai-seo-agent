"""Backward-compatible facade — re-exports all AI client symbols.

All code has been split into:
  - constants.py     — prompt templates, model defaults, field mappings
  - helpers.py       — response parsing, thinking extraction, utility functions
  - requests.py      — request builder functions
  - base.py          — BaseAIClient + NoneAIClient
  - anthropic_client.py — AnthropicAIClient (native Anthropic Messages API)
  - openai_compat.py — OpenAICompatibleClient (OpenAI, Gemini, Ollama, LM Studio, etc.)

This file re-exports everything so existing imports continue to work.
"""

import logging

from core.ai.constants import (
    DEFAULT_MODELS,
    FIELD_MAX_OUTPUT_TOKENS,
    FIELD_PROMPT_TEMPLATES,
    FIELD_RESULT_KEYS,
    PROVIDER_BASE_URLS,
    SYSTEM_PROMPT_EN,
    SYSTEM_PROMPT_TR,
    USER_PROMPT_TEMPLATE,
)
from core.ai.helpers import (
    _LMStudioNativeUnavailable,
    _cap_field_max_tokens,
    _extract_lm_studio_output,
    _extract_thinking,
    _get_system_prompt,
    _is_placeholder_json,
    _lm_studio_native_base_url,
    _merge_thinking_text,
    _parse_response_text,
)
from core.ai.requests import (
    _build_field_prompt,
    _build_suggestion,
    _prepare_prompt_descriptions,
    build_en_translation_request,
    build_field_rewrite_request,
    build_geo_rewrite_request,
    build_product_rewrite_request,
)
from core.ai.base import BaseAIClient, NoneAIClient
from core.ai.anthropic_client import AnthropicAIClient
from core.ai.openai_compat import OpenAICompatibleClient

logger = logging.getLogger(__name__)


def create_ai_client(config) -> BaseAIClient:
    """Factory: return the right AI client based on config.ai_provider."""
    provider = config.ai_provider.lower()

    if provider == "none":
        return NoneAIClient()
    elif provider == "anthropic":
        return AnthropicAIClient(config)
    elif provider in ("openai", "gemini", "openrouter", "ollama", "lm-studio", "custom"):
        return OpenAICompatibleClient(config, provider)
    else:
        logger.warning(f"Unknown AI provider '{provider}', defaulting to NoneAIClient")
        return NoneAIClient()


# Re-export everything for backward compatibility
__all__ = [
    # Constants
    "DEFAULT_MODELS",
    "FIELD_MAX_OUTPUT_TOKENS",
    "FIELD_PROMPT_TEMPLATES",
    "FIELD_RESULT_KEYS",
    "PROVIDER_BASE_URLS",
    "SYSTEM_PROMPT_EN",
    "SYSTEM_PROMPT_TR",
    "USER_PROMPT_TEMPLATE",
    # Helpers
    "_LMStudioNativeUnavailable",
    "_cap_field_max_tokens",
    "_extract_lm_studio_output",
    "_extract_thinking",
    "_get_system_prompt",
    "_is_placeholder_json",
    "_lm_studio_native_base_url",
    "_merge_thinking_text",
    "_parse_response_text",
    # Request builders
    "_build_field_prompt",
    "_build_suggestion",
    "_prepare_prompt_descriptions",
    "build_en_translation_request",
    "build_field_rewrite_request",
    "build_geo_rewrite_request",
    "build_product_rewrite_request",
    # Client classes
    "BaseAIClient",
    "NoneAIClient",
    "AnthropicAIClient",
    "OpenAICompatibleClient",
    # Factory
    "create_ai_client",
]

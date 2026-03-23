"""Anthropic Claude AI client using the native Messages API.

Supports extended thinking, request cancellation, and streaming.
"""

import logging
import threading
from typing import List, Optional

from core.models import AppConfig, Product, SeoScore, SeoSuggestion
from core.ai.base import BaseAIClient
from core.ai.constants import DEFAULT_MODELS, FIELD_RESULT_KEYS
from core.ai.helpers import _extract_thinking, _parse_response_text, _merge_thinking_text
from core.ai.requests import (
    build_product_rewrite_request,
    build_geo_rewrite_request,
    build_field_rewrite_request,
    build_en_translation_request,
    _build_suggestion,
)

logger = logging.getLogger(__name__)


class AnthropicAIClient(BaseAIClient):
    """Claude AI client using the native Anthropic Messages API.

    Supports extended thinking, request cancellation, and streaming.
    """

    def __init__(self, config: AppConfig) -> None:
        import anthropic as _anthropic

        api_key = config.ai_api_key or config.anthropic_api_key
        self._client = _anthropic.Anthropic(api_key=api_key)
        self._model = config.ai_model_name or DEFAULT_MODELS["anthropic"]
        self._max_tokens = config.ai_max_tokens
        self._config = config
        self._thinking_mode = config.ai_thinking_mode
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._cancel_lock = threading.Lock()
        self._active_stream = None
        self._last_response_meta: dict = {}

    @property
    def total_tokens(self) -> dict:
        return {
            "input": self._total_input_tokens,
            "output": self._total_output_tokens,
            "estimated_cost": self._estimate_cost(),
        }

    @property
    def last_response_meta(self) -> dict:
        return self._last_response_meta

    def _estimate_cost(self) -> float:
        model = self._model.lower()
        if "opus" in model:
            return round(
                self._total_input_tokens * 15.0 / 1_000_000
                + self._total_output_tokens * 75.0 / 1_000_000,
                4,
            )
        elif "sonnet" in model:
            return round(
                self._total_input_tokens * 3.0 / 1_000_000
                + self._total_output_tokens * 15.0 / 1_000_000,
                4,
            )
        else:  # haiku
            return round(
                self._total_input_tokens * 0.80 / 1_000_000
                + self._total_output_tokens * 4.0 / 1_000_000,
                4,
            )

    def _build_create_kwargs(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
    ) -> dict:
        """Build kwargs for messages.create(), adding thinking params when enabled."""
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if self._thinking_mode:
            # Extended thinking requires temperature=1 and uses a budget_tokens param
            thinking_budget = max(1024, max_tokens)
            kwargs["temperature"] = 1
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }
            # Increase max_tokens to accommodate thinking + response
            kwargs["max_tokens"] = max(max_tokens * 4, 8192)
        return kwargs

    def _extract_response(self, response) -> tuple[str, str]:
        """Extract text and thinking content from an Anthropic response.

        Returns (text_content, thinking_text).
        """
        text_parts: list[str] = []
        thinking_parts: list[str] = []

        for block in response.content:
            if block.type == "thinking":
                thinking_parts.append(block.thinking)
            elif block.type == "text":
                text_parts.append(block.text)

        text = "\n".join(text_parts)
        thinking = "\n\n".join(thinking_parts)

        # Also extract <think> tags from text if not using native thinking
        if not thinking:
            parsed_thinking, cleaned_text = _extract_thinking(text)
            if parsed_thinking:
                return cleaned_text, parsed_thinking

        return text, thinking

    def _track_response(self, response, label: str = "API") -> None:
        """Track token usage and log the response."""
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        self._last_response_meta = {
            "model": response.model,
            "stop_reason": response.stop_reason,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        logger.info(
            f"Anthropic {label}: {response.usage.input_tokens} input, "
            f"{response.usage.output_tokens} output tokens"
        )

    def cancel_active_request(self) -> bool:
        """Cancel the active streaming request if one is in flight."""
        with self._cancel_lock:
            stream = self._active_stream
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
                self._active_stream = None
                return True
        return False

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        request = build_product_rewrite_request(
            self._config, "anthropic", product, score, target_keywords,
        )
        kwargs = self._build_create_kwargs(
            request["system_prompt"], request["user_prompt"], request["max_tokens"],
        )
        response = self._client.messages.create(**kwargs)
        self._track_response(response, "rewrite")
        raw_text, thinking_text = self._extract_response(response)
        result, extra_thinking = _parse_response_text(raw_text)
        thinking_text = _merge_thinking_text(thinking_text, extra_thinking)
        return _build_suggestion(product, result, thinking_text)

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> str | tuple[str, str]:
        request = build_field_rewrite_request(
            self._config, "anthropic", field, product, target_keywords,
        )
        kwargs = self._build_create_kwargs(
            request["system_prompt"], request["user_prompt"], request["max_tokens"],
        )
        response = self._client.messages.create(**kwargs)
        self._track_response(response, f"field:{field}")
        raw_text, thinking_text = self._extract_response(response)
        result, extra_thinking = _parse_response_text(raw_text)
        thinking_text = _merge_thinking_text(thinking_text, extra_thinking)
        result_key = FIELD_RESULT_KEYS.get(field, field)
        value = result.get(result_key, "")
        if thinking_text:
            return value, thinking_text
        return value

    def rewrite_product_for_geo(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        request = build_geo_rewrite_request(
            self._config, "anthropic", product, score, target_keywords,
        )
        kwargs = self._build_create_kwargs(
            request["system_prompt"], request["user_prompt"], request["max_tokens"],
        )
        response = self._client.messages.create(**kwargs)
        self._track_response(response, "GEO rewrite")
        raw_text, thinking_text = self._extract_response(response)
        result, extra_thinking = _parse_response_text(raw_text)
        thinking_text = _merge_thinking_text(thinking_text, extra_thinking)
        return _build_suggestion(product, result, thinking_text)

    def translate_description_to_en(self, product: Product) -> str | tuple[str, str]:
        request = build_en_translation_request(
            self._config, "anthropic", product,
        )
        kwargs = self._build_create_kwargs(
            request["system_prompt"], request["user_prompt"], request["max_tokens"],
        )
        response = self._client.messages.create(**kwargs)
        self._track_response(response, "EN translation")
        raw_text, thinking_text = self._extract_response(response)
        result, extra_thinking = _parse_response_text(raw_text)
        thinking_text = _merge_thinking_text(thinking_text, extra_thinking)
        value = result.get("suggested_description_en", "")
        if thinking_text:
            return value, thinking_text
        return value

    def stream_message(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None):
        """Stream a message response, yielding text chunks.

        Yields tuples of (event_type, content) where event_type is
        'text', 'thinking', or 'done'.
        """
        effective_max = max_tokens or self._max_tokens
        kwargs = self._build_create_kwargs(system_prompt, user_prompt, effective_max)
        kwargs["stream"] = True

        with self._client.messages.stream(**{k: v for k, v in kwargs.items() if k != "stream"}) as stream:
            with self._cancel_lock:
                self._active_stream = stream

            try:
                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_start":
                            block = event.content_block
                            if hasattr(block, "type") and block.type == "thinking":
                                yield ("thinking_start", "")
                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "type"):
                                if delta.type == "thinking_delta":
                                    yield ("thinking", delta.thinking)
                                elif delta.type == "text_delta":
                                    yield ("text", delta.text)
                        elif event.type == "message_stop":
                            pass

                final_message = stream.get_final_message()
                self._track_response(final_message, "stream")
                yield ("done", "")
            finally:
                with self._cancel_lock:
                    if self._active_stream is stream:
                        self._active_stream = None

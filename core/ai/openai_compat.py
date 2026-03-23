"""OpenAI-compatible AI client for multiple providers.

Handles OpenAI, Gemini, OpenRouter, Ollama, LM Studio, and custom endpoints.
"""

import json
import logging
import threading
from typing import List, Optional

import httpx

from core.models import AppConfig, Product, SeoScore, SeoSuggestion
from core.ai.base import BaseAIClient
from core.ai.constants import DEFAULT_MODELS, PROVIDER_BASE_URLS, FIELD_RESULT_KEYS
from core.ai.helpers import (
    _parse_response_text,
    _merge_thinking_text,
    _lm_studio_native_base_url,
    _extract_lm_studio_output,
    _LMStudioNativeUnavailable,
)
from core.ai.requests import (
    build_product_rewrite_request,
    build_geo_rewrite_request,
    build_field_rewrite_request,
    build_en_translation_request,
    _build_suggestion,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(BaseAIClient):
    """Handles OpenAI, Gemini (OpenAI-compat), OpenRouter, Ollama, and Custom endpoints."""

    def __init__(self, config: AppConfig, provider: str) -> None:
        from openai import OpenAI

        self._provider = provider
        self._config = config

        # Resolve base URL
        if provider == "custom":
            base_url = config.ai_base_url or None
        elif config.ai_base_url:
            base_url = config.ai_base_url
        else:
            base_url = PROVIDER_BASE_URLS.get(provider)

        # Ensure /v1 suffix for OpenAI-compatible providers
        if base_url and provider in ("ollama", "lm-studio", "openai") and not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
            logger.info(f"Auto-appended /v1 to base URL: {base_url}")

        # Ollama and LM Studio don't need a real API key
        api_key = config.ai_api_key or ("ollama" if provider in ("ollama", "lm-studio") else "no-key")

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = config.ai_model_name or DEFAULT_MODELS.get(provider, "gpt-4o-mini")
        self._temperature = config.ai_temperature
        self._max_tokens = config.ai_max_tokens
        self._lm_studio_native_base = (
            _lm_studio_native_base_url(base_url or PROVIDER_BASE_URLS["lm-studio"])
            if provider == "lm-studio"
            else ""
        )
        # Token tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._last_input_tokens = 0
        self._last_output_tokens = 0
        self._last_response_meta: dict = {}
        self._active_request_lock = threading.Lock()
        self._active_lm_studio_client: httpx.Client | None = None
        self._active_lm_studio_response: httpx.Response | None = None
        self._cancel_lm_studio_request = False

    @property
    def total_tokens(self) -> dict:
        return {
            "input": self._total_input_tokens,
            "output": self._total_output_tokens,
            "estimated_cost": 0.0,
        }

    @property
    def last_usage(self) -> dict:
        """Token usage of the most recent API call."""
        return {
            "input": self._last_input_tokens,
            "output": self._last_output_tokens,
        }

    @property
    def last_response_meta(self) -> dict:
        return dict(self._last_response_meta)

    def _track_usage(self, response) -> None:
        """Extract and accumulate token usage from an API response."""
        usage = response.usage
        if usage:
            inp = getattr(usage, 'prompt_tokens', 0) or 0
            out = getattr(usage, 'completion_tokens', 0) or 0
            total = getattr(usage, 'total_tokens', 0) or 0
            self._last_input_tokens = inp
            self._last_output_tokens = out
            self._last_response_meta = {
                "input_tokens": inp,
                "output_tokens": out,
                "total_tokens": total,
            }
            self._total_input_tokens += inp
            self._total_output_tokens += out
            logger.info(
                f"Token kullanimi: {inp} input + {out} output = {total} "
                f"(toplam: {self._total_input_tokens}+{self._total_output_tokens})"
            )
        else:
            self._last_input_tokens = 0
            self._last_output_tokens = 0
            self._last_response_meta = {}
            logger.warning(f"{self._provider}: response.usage is None — token tracking unavailable")

    def _track_native_usage(self, data: dict) -> None:
        stats = data.get("stats") or {}
        inp = int(stats.get("input_tokens", 0) or 0)
        out = int(stats.get("total_output_tokens", 0) or 0)
        self._last_input_tokens = inp
        self._last_output_tokens = out
        self._last_response_meta = {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
            "reasoning_output_tokens": int(stats.get("reasoning_output_tokens", 0) or 0),
            "tokens_per_second": stats.get("tokens_per_second"),
            "time_to_first_token_seconds": stats.get("time_to_first_token_seconds"),
            "stop_reason": data.get("stop_reason") or stats.get("stop_reason") or "",
            "model_instance_id": data.get("model_instance_id", ""),
            "model": self._model,
        }
        self._total_input_tokens += inp
        self._total_output_tokens += out
        logger.info(
            f"LM Studio native token kullanimi: {inp} input + {out} output "
            f"(toplam: {self._total_input_tokens}+{self._total_output_tokens})"
        )

    def _lm_studio_headers(self) -> dict:
        api_key = (self._config.ai_api_key or "").strip()
        if api_key and api_key not in {"ollama", "lm-studio"}:
            return {"Authorization": f"Bearer {api_key}"}
        return {}

    def _post_lm_studio_native(self, payload: dict) -> dict:
        url = f"{self._lm_studio_native_base}/api/v1/chat"
        timeout = httpx.Timeout(120.0, connect=5.0)
        client = httpx.Client(timeout=timeout)
        with self._active_request_lock:
            self._active_lm_studio_client = client
            self._cancel_lm_studio_request = False

        try:
            stream_payload = dict(payload)
            stream_payload["stream"] = True

            try:
                with client.stream("POST", url, json=stream_payload, headers=self._lm_studio_headers()) as response:
                    with self._active_request_lock:
                        self._active_lm_studio_response = response
                        cancel_requested = self._cancel_lm_studio_request

                    if cancel_requested:
                        response.close()
                        raise RuntimeError("LM Studio istegi kullanici tarafindan iptal edildi")

                    if response.status_code in (404, 405, 501):
                        raise _LMStudioNativeUnavailable("LM Studio native /api/v1/chat endpoint'i mevcut degil")

                    if response.status_code >= 400 and "reasoning" in payload:
                        retry_payload = dict(payload)
                        retry_payload.pop("reasoning", None)
                        return self._post_lm_studio_native(retry_payload)

                    if response.status_code >= 400:
                        error_text = response.read().decode("utf-8", errors="replace")
                        raise RuntimeError(
                            f"LM Studio native API hatasi ({response.status_code}): {error_text[:300]}"
                        )

                    event_name = ""
                    data_lines: list[str] = []
                    for line in response.iter_lines():
                        if line == "":
                            if event_name == "chat.end" and data_lines:
                                try:
                                    payload_data = json.loads("\n".join(data_lines))
                                except json.JSONDecodeError as exc:
                                    raise RuntimeError("LM Studio stream sonu JSON degildi") from exc
                                return payload_data.get("result", payload_data)
                            event_name = ""
                            data_lines = []
                            continue

                        if line.startswith("event: "):
                            event_name = line[7:]
                        elif line.startswith("data: "):
                            data_lines.append(line[6:])
            except httpx.HTTPError as exc:
                raise RuntimeError(f"LM Studio native API istegi basarisiz: {exc}") from exc

            raise RuntimeError("LM Studio native stream chat.end olayi dondurmedi")
        finally:
            with self._active_request_lock:
                if self._active_lm_studio_response is not None:
                    self._active_lm_studio_response = None
                if self._active_lm_studio_client is client:
                    self._active_lm_studio_client = None
                self._cancel_lm_studio_request = False
            client.close()

    def cancel_active_request(self) -> bool:
        with self._active_request_lock:
            self._cancel_lm_studio_request = True
            response = self._active_lm_studio_response
            client = self._active_lm_studio_client
        if response is None and client is None:
            return False
        try:
            if response is not None:
                response.close()
            if client is not None:
                client.close()
            return True
        except Exception:
            logger.exception("Active LM Studio request could not be cancelled cleanly")
            return False

    def _lm_studio_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        thinking_mode: bool,
    ) -> tuple[str, str]:
        payload = {
            "model": self._model,
            "system_prompt": system_prompt,
            "input": user_prompt,
            "temperature": self._temperature,
            "max_output_tokens": max_tokens,
            "reasoning": "on" if thinking_mode else "off",
        }
        data = self._post_lm_studio_native(payload)
        self._track_native_usage(data)
        raw_text, native_thinking = _extract_lm_studio_output(data)
        if not raw_text.strip():
            stats = data.get("stats") or {}
            reasoning_tokens = int(stats.get("reasoning_output_tokens", 0) or 0)
            total_output = int(stats.get("total_output_tokens", 0) or 0)
            if thinking_mode and reasoning_tokens >= total_output > 0:
                raise ValueError(
                    "LM Studio thinking ciktilari token butcesini tuketti; model JSON yanitina gecemedi. "
                    "Max Tokens degerini artirin, context length'i buyutun veya Thinking Mode'u kapatin."
                )
            raise ValueError(
                "LM Studio yaniti JSON icerik uretmeden tamamlandi. "
                "Max Tokens degerini artirin veya Thinking Mode'u kapatin."
            )
        return raw_text, native_thinking

    def _call_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        label: str = "API",
    ) -> tuple[str, str]:
        """Shared completion call: try LM Studio native first, fall back to OpenAI-compat.

        Returns (raw_text, thinking_text_from_lm_studio_native_or_empty).
        """
        thinking_mode = self._config.ai_thinking_mode

        if self._provider == "lm-studio":
            try:
                raw_text, native_thinking = self._lm_studio_chat(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    thinking_mode=thinking_mode,
                )
                return raw_text, native_thinking
            except _LMStudioNativeUnavailable:
                logger.warning(
                    "LM Studio native REST API kullanilamadi; OpenAI-compatible /v1 yoluna geri dusuluyor"
                )

        create_kwargs = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        try:
            response = self._client.chat.completions.create(**create_kwargs)
        except Exception as api_err:
            logger.error(f"{self._provider} {label} failed: {api_err}")
            raise

        self._track_usage(response)

        finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
        self._last_response_meta["finish_reason"] = finish_reason or ""
        self._last_response_meta["model"] = self._model
        if finish_reason == "length":
            logger.warning(
                f"{self._provider}: {label} response truncated (max_tokens={max_tokens}). "
                "Consider increasing Max Tokens or disabling Thinking Mode."
            )

        if not response.choices:
            raise ValueError(f"{self._provider} yanit dondurmedi (choices bos)")

        message = response.choices[0].message
        raw_text = (message.content or "") if message else ""
        if not raw_text.strip():
            raise ValueError(f"{self._provider} bos icerik dondu")

        logger.debug(f"{self._provider} {label} response: {raw_text[:500]}")
        return raw_text, ""

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        request = build_product_rewrite_request(
            self._config, self._provider, product, score, target_keywords,
        )
        raw_text, native_thinking = self._call_completion(
            request["system_prompt"], request["user_prompt"], request["max_tokens"], "rewrite",
        )
        result, parsed_thinking = _parse_response_text(raw_text)
        return _build_suggestion(product, result, _merge_thinking_text(native_thinking, parsed_thinking))

    def rewrite_product_for_geo(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        request = build_geo_rewrite_request(
            self._config, self._provider, product, score, target_keywords,
        )
        raw_text, native_thinking = self._call_completion(
            request["system_prompt"], request["user_prompt"], request["max_tokens"], "GEO rewrite",
        )
        result, parsed_thinking = _parse_response_text(raw_text)
        return _build_suggestion(product, result, _merge_thinking_text(native_thinking, parsed_thinking))

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> str | tuple[str, str]:
        request = build_field_rewrite_request(
            self._config, self._provider, field, product, target_keywords,
        )
        raw_text, native_thinking = self._call_completion(
            request["system_prompt"], request["user_prompt"], request["max_tokens"], f"field:{field}",
        )
        result, parsed_thinking = _parse_response_text(raw_text)
        thinking_text = _merge_thinking_text(native_thinking, parsed_thinking)
        result_key = FIELD_RESULT_KEYS.get(field, field)
        value = result.get(result_key, "")
        if thinking_text:
            return value, thinking_text
        return value

    def translate_description_to_en(self, product: Product) -> str | tuple[str, str]:
        request = build_en_translation_request(
            self._config, self._provider, product,
        )
        raw_text, native_thinking = self._call_completion(
            request["system_prompt"], request["user_prompt"], request["max_tokens"], "EN translation",
        )
        result, parsed_thinking = _parse_response_text(raw_text)
        thinking_text = _merge_thinking_text(native_thinking, parsed_thinking)
        value = result.get("suggested_description_en", "")
        if thinking_text:
            return value, thinking_text
        return value

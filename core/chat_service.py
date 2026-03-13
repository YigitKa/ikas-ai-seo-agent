"""Compatibility facade for chat service and helper exports."""

from core.chat_service_state_mixin import ChatServiceStateMixin
from core.chat_service_suggestion_mixin import ChatServiceSuggestionMixin
from core.chat_service_streaming_mixin import ChatServiceStreamingMixin

# Re-export helper symbols used by tests and other modules.
from core.chat_service_support import (  # noqa: F401
    SAVE_SEO_SUGGESTION_TOOL_NAME,
    _LMStudioNativeUnavailable,
    _StreamingVisibleTextFilter,
    _append_false_action_disclaimer,
    _append_operation_suggestion,
    _build_completion_meta,
    _build_product_context,
    _has_mutation_tool_result,
)


class ChatService(
    ChatServiceStateMixin,
    ChatServiceSuggestionMixin,
    ChatServiceStreamingMixin,
):
    """Multi-turn chat service with MCP + local tool orchestration."""


__all__ = [
    "ChatService",
    "SAVE_SEO_SUGGESTION_TOOL_NAME",
    "_LMStudioNativeUnavailable",
    "_StreamingVisibleTextFilter",
    "_append_false_action_disclaimer",
    "_append_operation_suggestion",
    "_build_completion_meta",
    "_build_product_context",
    "_has_mutation_tool_result",
]

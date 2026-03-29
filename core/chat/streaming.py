from core.chat.streaming_flow import ChatServiceStreamingFlowMixin
from core.chat.streaming_lm_studio import ChatServiceStreamingLMStudioMixin
from core.chat.streaming_messages import ChatServiceStreamingMessagesMixin
from core.chat.streaming_provider import ChatServiceStreamingProviderMixin


class ChatServiceStreamingMixin(
    ChatServiceStreamingMessagesMixin,
    ChatServiceStreamingFlowMixin,
    ChatServiceStreamingProviderMixin,
    ChatServiceStreamingLMStudioMixin,
):
    """Streaming and completion orchestration mixin composed from smaller modules."""

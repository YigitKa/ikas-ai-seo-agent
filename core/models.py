from datetime import datetime
from typing import Any, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


STORE_MEMORY_TYPES = (
    "brand_tone",
    "forbidden_claim",
    "category_glossary",
    "approved_preference",
    "operation_note",
)


def _summarize_store_memory_text(value: str, limit: int = 220) -> str:
    compact = " ".join(str(value or "").split()).strip()
    if len(compact) <= limit:
        return compact
    truncated = compact[:limit].rsplit(" ", 1)[0].strip()
    return (truncated or compact[:limit].strip()) + "..."


class Product(BaseModel):
    id: str
    name: str
    slug: Optional[str] = None
    description: str = ""
    description_translations: dict[str, str] = Field(default_factory=dict)
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    price: Optional[float] = None
    sku: Optional[str] = None
    status: str = "active"
    image_url: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)


class SeoScore(BaseModel):
    product_id: str
    total_score: int = Field(ge=0, le=100)
    seo_score: int = Field(ge=0, le=100, default=0)
    geo_score: int = Field(ge=0, le=100, default=0)
    aeo_score: int = Field(ge=0, le=100, default=0)
    title_score: int = Field(ge=0, le=15)
    description_score: int = Field(ge=0, le=20)
    english_description_score: int = Field(ge=0, le=5, default=0)
    meta_score: int = Field(ge=0, le=15)
    meta_desc_score: int = Field(ge=0, le=10)
    keyword_score: int = Field(ge=0, le=10)
    content_quality_score: int = Field(ge=0, le=10, default=0)
    technical_seo_score: int = Field(ge=0, le=10, default=0)
    readability_score: int = Field(ge=0, le=5, default=0)
    ai_citability_score: int = Field(ge=0, le=10, default=0)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _populate_summary_scores(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        def _normalize(raw_score: int | float, max_score: int) -> int:
            if max_score <= 0:
                return 0
            normalized = round((max(0, raw_score) / max_score) * 100)
            return max(0, min(100, normalized))

        if "seo_score" not in value:
            value["seo_score"] = _normalize(
                int(value.get("title_score", 0))
                + int(value.get("meta_score", 0))
                + int(value.get("meta_desc_score", 0))
                + int(value.get("keyword_score", 0))
                + int(value.get("technical_seo_score", 0)),
                60,
            )

        if "aeo_score" not in value:
            value["aeo_score"] = _normalize(
                int(value.get("description_score", 0))
                + int(value.get("english_description_score", 0))
                + int(value.get("content_quality_score", 0))
                + int(value.get("readability_score", 0)),
                40,
            )

        if "geo_score" not in value:
            value["geo_score"] = _normalize(int(value.get("ai_citability_score", 0)), 10)

        return value

    @property
    def needs_optimization(self) -> bool:
        return self.total_score < 70


class SeoSuggestion(BaseModel):
    product_id: str
    original_name: str
    suggested_name: Optional[str] = None
    original_description: str
    suggested_description: str = ""
    original_description_en: str = ""
    suggested_description_en: str = ""
    original_meta_title: Optional[str] = None
    suggested_meta_title: str = ""
    original_meta_description: Optional[str] = None
    suggested_meta_description: str = ""
    thinking_text: str = ""
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)


class ChatMessage(BaseModel):
    """A single message in a multi-turn chat conversation."""
    role: str = "user"  # user | assistant | system | tool
    content: str = ""
    tool_calls: List[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatResponse(BaseModel):
    """Response from the chat service."""
    content: str = ""
    thinking: str = ""
    tool_results: List[dict[str, Any]] = Field(default_factory=list)
    error: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)
    suggestion_saved: dict[str, Any] | None = None
    pending_suggestion: SeoSuggestion | None = None


class AppConfig(BaseModel):
    ikas_store_name: str = ""
    ikas_client_id: str = ""
    ikas_client_secret: str = ""
    ikas_api_url: str = ""
    # ikas MCP integration
    ikas_mcp_token: str = ""
    # Legacy Anthropic key (backward compat)
    anthropic_api_key: str = ""
    store_language: str = "tr"
    store_languages: List[str] = Field(default_factory=lambda: ["tr"])
    seo_target_keywords: List[str] = Field(default_factory=list)
    dry_run: bool = True
    log_level: str = "INFO"
    # Multi-provider AI settings
    ai_provider: str = "none"  # anthropic | openai | gemini | openrouter | ollama | custom | none
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model_name: str = ""
    ai_temperature: float = 0.7
    ai_max_tokens: int = 2000
    ai_thinking_mode_chat: bool = False
    ai_thinking_mode_batch: bool = False
    seo_low_score_threshold: int = 70
    # Google Search Console OAuth2
    gsc_client_id: str = ""
    gsc_client_secret: str = ""
    gsc_refresh_token: str = ""   # OAuth2 akışından sonra otomatik saklanır
    gsc_property_url: str = ""    # Örn: https://www.mystore.com

    @property
    def ai_thinking_mode(self) -> bool:
        """Backward-compat alias — returns batch setting."""
        return self.ai_thinking_mode_batch


# ── Agent Architecture Models ────────────────────────────────────────────


class AgentToolCall(BaseModel):
    """Record of a single tool invocation during an agent run."""
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    duration_ms: int = 0


class AgentEvent(BaseModel):
    """Streaming event emitted by AgentOrchestrator."""
    type: str  # thinking | tool_call | tool_result | response_chunk | completed | error
    content: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_result: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Final result of an agent run."""
    content: str
    thinking: str = ""
    tool_calls_made: List[AgentToolCall] = Field(default_factory=list)
    iterations: int = 0
    meta: dict[str, Any] = Field(default_factory=dict)
    suggestion_saved: dict[str, Any] | None = None


class CompetitorPrice(BaseModel):
    """Tek bir rakip urun sonucu."""
    site_name: str
    product_name: str
    price: float
    currency: str = "TRY"
    url: str


class CompetitorPriceReport(BaseModel):
    """Rakip fiyat arastirma raporu."""
    product_id: str
    product_name: str
    query_used: str
    our_price: float | None = None
    competitors: List[CompetitorPrice] = Field(default_factory=list)
    lowest_price: float | None = None
    highest_price: float | None = None
    average_price: float | None = None
    price_position: str = ""
    price_difference_pct: float | None = None
    recommendation: str = ""
    competitor_count: int = 0
    cached: bool = False
    searched_at: datetime = Field(default_factory=datetime.now)


class TaskError(BaseModel):
    code: str = ""
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(BaseModel):
    id: str
    type: str
    status: str
    progress: int = Field(default=0, ge=0, le=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: TaskError | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None


class StoreMemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    memory_type: str
    title: str = ""
    content: str = ""
    summary: str = ""
    category: str = ""
    source: str = "manual"
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="before")
    @classmethod
    def _normalize_memory(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        memory_type = str(value.get("memory_type") or "").strip().lower()
        if memory_type not in STORE_MEMORY_TYPES:
            raise ValueError(
                "memory_type gecersiz. Beklenen tipler: "
                + ", ".join(STORE_MEMORY_TYPES)
            )
        value["memory_type"] = memory_type

        content = " ".join(str(value.get("content") or "").split()).strip()
        if not content:
            raise ValueError("content bos olamaz")
        value["content"] = content

        title = " ".join(str(value.get("title") or "").split()).strip()
        value["title"] = title or _summarize_store_memory_text(content, limit=72)

        summary = " ".join(str(value.get("summary") or "").split()).strip()
        value["summary"] = summary or _summarize_store_memory_text(content, limit=220)
        value["category"] = " ".join(str(value.get("category") or "").split()).strip()
        value["source"] = " ".join(str(value.get("source") or "manual").split()).strip() or "manual"
        return value


class StoreMemoryUsageLog(BaseModel):
    enabled: bool = False
    applies_to: str = "chat"
    agent_type: str = ""
    entry_count: int = 0
    char_count: int = 0
    truncated: bool = False
    omitted_entries: int = 0
    used_memory_ids: list[str] = Field(default_factory=list)
    used_types: list[str] = Field(default_factory=list)
    category_matches: int = 0


class StoreMemoryContext(BaseModel):
    prompt: str = ""
    entries: list[StoreMemoryEntry] = Field(default_factory=list)
    usage_log: StoreMemoryUsageLog = Field(default_factory=StoreMemoryUsageLog)


# ── llms.txt generation models ─────────────────────────────────────────────────


class LlmsJob(BaseModel):
    id: str
    task_id: str | None = None
    status: str
    total_count: int
    processed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class LlmsEntry(BaseModel):
    id: int
    job_id: str
    product_id: str
    summary: str = ""
    status: str = "pending"  # pending | processing | done | failed
    error: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    created_at: datetime
    updated_at: datetime

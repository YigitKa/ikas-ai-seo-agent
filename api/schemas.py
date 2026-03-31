"""API request/response schemas — thin wrappers over core models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from core.models import Product, SeoScore, SeoSuggestion, TaskRecord


# ── Generic ──────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    ok: bool = True


# ── Products ─────────────────────────────────────────────────────────────────

class ProductWithScore(BaseModel):
    product: Product
    score: Optional[SeoScore] = None


class ProductListResponse(BaseModel):
    items: list[ProductWithScore]
    total_count: int
    page: int
    limit: int


class FetchProductsRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    page: int = Field(default=1, ge=1)


class ProductSyncResponse(BaseModel):
    fetched_count: int
    total_count: int


class LocalDataResetResponse(BaseModel):
    message: str
    products_deleted: int
    scores_deleted: int
    suggestions_deleted: int
    logs_deleted: int


# ── SEO ──────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list)


class ScoreResponse(BaseModel):
    product_id: str
    score: SeoScore


class GeoAuditRequest(BaseModel):
    url: str
    max_pages: int = Field(default=8, ge=1, le=30)


class GeoAuditResponse(BaseModel):
    url: str
    timestamp: str
    discovery: dict[str, Any]
    analysis: dict[str, Any]
    synthesis: dict[str, Any]
    report_markdown: str


# ── Suggestions ──────────────────────────────────────────────────────────────

class GenerateSuggestionRequest(BaseModel):
    product_id: str


class FieldRewriteRequest(BaseModel):
    product_id: str
    field: str


class SuggestionActionRequest(BaseModel):
    product_id: str


class SuggestionFieldUpdate(BaseModel):
    field: str
    value: str


class SuggestionUpdateRequest(BaseModel):
    product_id: str
    fields: list[SuggestionFieldUpdate]


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0


class RewriteResponse(BaseModel):
    suggestion: Optional[SeoSuggestion] = None
    field_value: str = ""
    thinking_text: str = ""
    token_usage: Optional[TokenUsage] = None


class ApplyResponse(BaseModel):
    applied: int
    total: int


# ── Settings ─────────────────────────────────────────────────────────────────

class SettingsResponse(BaseModel):
    store_name: str = ""
    client_id: str = ""
    client_secret: str = ""
    mcp_token: str = ""
    ai_provider: str = "none"
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model_name: str = ""
    ai_temperature: float = 0.7
    ai_max_tokens: int = 2000
    ai_thinking_mode_chat: bool = False
    ai_thinking_mode_batch: bool = False
    languages: str = "tr"
    keywords: str = ""
    dry_run: bool = True


class SettingsUpdateRequest(BaseModel):
    values: dict[str, Any]


class PromptTemplateResponse(BaseModel):
    key: str
    title: str
    description: str
    variables: list[str] = Field(default_factory=list)
    runtime_variables: list[str] = Field(default_factory=list)
    height: int = 150
    content: str = ""


class PromptGroupResponse(BaseModel):
    label: str
    prompts: list[PromptTemplateResponse] = Field(default_factory=list)


class PromptTemplatesResponse(BaseModel):
    groups: list[PromptGroupResponse] = Field(default_factory=list)


class PromptTemplatesUpdateRequest(BaseModel):
    templates: dict[str, str]


class PromptResetRequest(BaseModel):
    prompt_keys: list[str] = Field(default_factory=list)


class PromptLayerResponse(BaseModel):
    order: int
    prompt_key: Optional[str] = None
    label: str
    description: str
    linked_keys: list[str] = Field(default_factory=list)


class PromptLayeringFlowResponse(BaseModel):
    id: str
    title: str
    description: str
    layers: list[PromptLayerResponse] = Field(default_factory=list)


class PromptLayeringOrderResponse(BaseModel):
    flows: list[PromptLayeringFlowResponse] = Field(default_factory=list)


class ProviderHealthResponse(BaseModel):
    status: str
    message: str


class TestConnectionResponse(BaseModel):
    ok: bool
    ikas_ok: bool = False
    message: str = ""


class ProviderModelsResponse(BaseModel):
    models: list[str]


class LMStudioModelStatusResponse(BaseModel):
    id: str = ""
    display_name: str = ""
    status: str = ""
    context_length: Optional[int] = None


class LMStudioDownloadStatusResponse(BaseModel):
    job_id: str = ""
    status: str = ""
    bytes_per_second: Optional[float] = None
    estimated_completion: str = ""
    completed_at: str = ""
    total_size_bytes: Optional[int] = None
    downloaded_bytes: Optional[int] = None
    started_at: str = ""


class LMStudioLiveStatusResponse(BaseModel):
    provider: str = "lm-studio"
    configured_model: str = ""
    selected_model: LMStudioModelStatusResponse = Field(default_factory=LMStudioModelStatusResponse)
    models: list[LMStudioModelStatusResponse] = Field(default_factory=list)
    download_status: Optional[LMStudioDownloadStatusResponse] = None


# ── MCP ──────────────────────────────────────────────────────────────────────

class MCPStatusResponse(BaseModel):
    has_token: bool = False
    initialized: bool = False
    tool_count: int = 0
    message: str = ""
    tools: list[dict[str, str]] = Field(default_factory=list)


class ChatMessageSchema(BaseModel):
    role: str
    content: str
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    thinking: str = ""
    error: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)


class TaskErrorResponse(BaseModel):
    code: str = ""
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: str
    type: str
    status: str
    progress: int
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: Optional[TaskErrorResponse] = None
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    heartbeat_at: Optional[str] = None

    @classmethod
    def from_record(cls, task: TaskRecord) -> "TaskResponse":
        return cls(
            id=task.id,
            type=task.type,
            status=task.status,
            progress=task.progress,
            payload=task.payload,
            result=task.result,
            error=TaskErrorResponse(**task.error.model_dump()) if task.error else None,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
            started_at=task.started_at.isoformat() if task.started_at else None,
            finished_at=task.finished_at.isoformat() if task.finished_at else None,
            heartbeat_at=task.heartbeat_at.isoformat() if task.heartbeat_at else None,
        )


class TaskListResponse(BaseModel):
    items: list[TaskResponse] = Field(default_factory=list)


# ── Batch Operations ──────────────────────────────────────────────────────────

ALL_TARGET_FIELDS = ["meta_title", "meta_description", "name", "description", "description_en"]


class BatchConfig(BaseModel):
    score_threshold: int = Field(default=70, ge=0, le=100)
    category_filter: str = ""
    in_stock_only: bool = False
    preserve_specs: bool = True
    prevent_cannibalization: bool = True
    max_title_change_pct: int = Field(default=20, ge=0, le=100)
    target_fields: list[str] = Field(default_factory=lambda: list(ALL_TARGET_FIELDS))


class BatchJobResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    status: str
    config: dict[str, Any]
    total_count: int
    processed_count: int
    skipped_count: int
    failed_count: int
    avg_score_before: float
    avg_score_after: float
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class BatchItemResponse(BaseModel):
    id: int
    job_id: str
    product_id: str
    product_name: str
    status: str
    score_before: Optional[int] = None
    score_after: Optional[int] = None
    skip_reason: Optional[str] = None
    has_rollback: bool = False
    suggestion_data: Optional[dict[str, Any]] = None


class BatchJobDetailResponse(BaseModel):
    job: BatchJobResponse
    items: list[BatchItemResponse]


class BatchStatsResponse(BaseModel):
    total_jobs: int
    total_processed: int
    avg_score_improvement: float
    active_job: Optional[BatchJobResponse] = None


class StartBatchRequest(BaseModel):
    config: BatchConfig
    product_ids: list[str] = Field(default_factory=list)


class BatchItemDecisionRequest(BaseModel):
    decision: str  # 'approved' | 'rejected' | 'revised'
    revised_data: Optional[dict[str, Any]] = None

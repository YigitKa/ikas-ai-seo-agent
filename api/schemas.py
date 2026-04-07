"""API request/response schemas — thin wrappers over core models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from core.models import Product, SeoScore, SeoSuggestion, StoreMemoryEntry, TaskRecord
from core.skills import SkillDefinition, SkillPromptLayer, SkillResolvedPromptLayer


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
    skill_slug: str = ""


class FieldRewriteRequest(BaseModel):
    product_id: str
    field: str
    skill_slug: str = ""


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


class StoreMemoryResponse(BaseModel):
    id: str
    memory_type: str
    title: str = ""
    content: str = ""
    summary: str = ""
    category: str = ""
    source: str = "manual"
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, memory: StoreMemoryEntry) -> "StoreMemoryResponse":
        return cls(
            id=memory.id,
            memory_type=memory.memory_type,
            title=memory.title,
            content=memory.content,
            summary=memory.summary,
            category=memory.category,
            source=memory.source,
            enabled=memory.enabled,
            metadata=memory.metadata,
            created_at=memory.created_at.isoformat(),
            updated_at=memory.updated_at.isoformat(),
        )


class StoreMemoriesResponse(BaseModel):
    items: list[StoreMemoryResponse] = Field(default_factory=list)


class StoreMemoryUpsertRequest(BaseModel):
    memory: StoreMemoryResponse


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


class SkillPromptLayerResponse(BaseModel):
    type: str = "inline"
    label: str = ""
    prompt_key: str = ""
    content: str = ""

    @classmethod
    def from_model(cls, layer: SkillPromptLayer) -> "SkillPromptLayerResponse":
        return cls(**layer.model_dump(mode="json"))


class SkillResolvedPromptLayerResponse(BaseModel):
    type: str = "inline"
    label: str = ""
    source: str = ""
    content: str = ""

    @classmethod
    def from_model(cls, layer: SkillResolvedPromptLayer) -> "SkillResolvedPromptLayerResponse":
        return cls(**layer.model_dump(mode="json"))


class SkillResponse(BaseModel):
    schema_version: int = 1
    slug: str
    name: str
    description: str = ""
    when_to_use: str = ""
    applies_to: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    prompt_layers: list[SkillPromptLayerResponse] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    priority: int = 100
    status: str = "active"
    instructions_markdown: str = ""
    source: str = "project"
    content_hash: str = ""
    is_default: bool = False

    @classmethod
    def from_model(cls, skill: SkillDefinition) -> "SkillResponse":
        payload = skill.model_dump(mode="json")
        payload["prompt_layers"] = [
            SkillPromptLayerResponse.from_model(SkillPromptLayer.model_validate(layer))
            for layer in payload.get("prompt_layers", [])
        ]
        payload.pop("path", None)
        return cls(**payload)


class SkillsResponse(BaseModel):
    items: list[SkillResponse] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)


class SkillUpsertRequest(BaseModel):
    skill: SkillResponse


class SkillValidationResponse(BaseModel):
    ok: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    resolved_prompt_layers: list[SkillResolvedPromptLayerResponse] = Field(default_factory=list)


class SkillPreviewDebugResponse(BaseModel):
    applies_to: str = "chat"
    tool_scope_mode: str = "prompt_and_tools"
    tool_scope_note: str = ""
    prompt_char_count: int = 0
    instruction_word_count: int = 0
    requested_tools: list[str] = Field(default_factory=list)
    resolved_tools: list[str] = Field(default_factory=list)
    flow_tools: list[str] = Field(default_factory=list)
    resolved_layer_count: int = 0


class SkillPreviewResponse(BaseModel):
    validation: SkillValidationResponse
    composed_prompt: str = ""
    debug: SkillPreviewDebugResponse = Field(default_factory=SkillPreviewDebugResponse)


class SkillImportRequest(BaseModel):
    skill: SkillResponse


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


# ── Diagnostics ──────────────────────────────────────────────────────────────

class DiagnosticsCheckResponse(BaseModel):
    name: str
    status: str = "unknown"
    checked_at: Optional[str] = None
    latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None
    retryable: Optional[bool] = None


class DiagnosticsIssueResponse(BaseModel):
    scope: str = "global"
    component: str = ""
    reason_code: str = ""
    summary: str = ""
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    recommended_action: Optional[str] = None


class DiagnosticsComponentResponse(BaseModel):
    status: str = "unknown"
    summary: str = ""
    checked_at: Optional[str] = None
    latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None
    retryable: Optional[bool] = None
    reason_codes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    checks: list[DiagnosticsCheckResponse] = Field(default_factory=list)


class DiagnosticsProviderResponse(DiagnosticsComponentResponse):
    provider: str = ""
    configured_model: str = ""
    message: str = ""


class DiagnosticsMCPResponse(DiagnosticsComponentResponse):
    has_token: bool = False
    initialized: bool = False
    tool_count: int = 0
    tool_names: list[str] = Field(default_factory=list)


class DiagnosticsDatabaseResponse(DiagnosticsComponentResponse):
    path: str = ""
    journal_mode: str = ""
    product_count: int = 0
    suggestion_count: int = 0
    task_count: int = 0
    write_test_ok: bool = False


class DiagnosticsWorkersResponse(DiagnosticsComponentResponse):
    active_count: int = 0
    waiting_count: int = 0
    stuck_count: int = 0
    latest_heartbeat_at: Optional[str] = None
    last_crash_summary: str = ""


class DiagnosticsPromptCacheResponse(DiagnosticsComponentResponse):
    prompt_dir: str = ""
    total_templates: int = 0
    loaded_templates: int = 0
    missing_templates: list[str] = Field(default_factory=list)


class DiagnosticsCountsResponse(BaseModel):
    total: int = 0
    processed: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    retried: int = 0
    remaining: int = 0


class DiagnosticsTaskSummaryResponse(BaseModel):
    id: str
    type: str
    status: str
    progress: int = 0
    stage: str = ""
    stage_label: str = ""
    status_message: str = ""
    heartbeat_at: Optional[str] = None
    updated_at: Optional[str] = None
    current_item: Optional[str] = None
    stuck: bool = False
    reason_code: Optional[str] = None
    counts: DiagnosticsCountsResponse = Field(default_factory=DiagnosticsCountsResponse)


class DiagnosticsTaskRuntimeResponse(DiagnosticsComponentResponse):
    queued_count: int = 0
    active_count: int = 0
    waiting_count: int = 0
    terminal_count: int = 0
    failed_count: int = 0
    stuck_count: int = 0
    longest_running_task: Optional[DiagnosticsTaskSummaryResponse] = None
    stuck_tasks: list[DiagnosticsTaskSummaryResponse] = Field(default_factory=list)


class DiagnosticsStoreContextResponse(DiagnosticsComponentResponse):
    store_name: str = ""
    languages: list[str] = Field(default_factory=list)
    dry_run: bool = True
    product_count: int = 0
    pending_suggestions: int = 0


class DiagnosticsActiveJobsResponse(DiagnosticsComponentResponse):
    total: int = 0
    items: list[DiagnosticsTaskSummaryResponse] = Field(default_factory=list)


class DiagnosticsSummaryResponse(BaseModel):
    overall_status: str = "unknown"
    generated_at: str
    reason_codes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    issues: list[DiagnosticsIssueResponse] = Field(default_factory=list)
    debug_report: str = ""
    providers: DiagnosticsProviderResponse = Field(default_factory=DiagnosticsProviderResponse)
    mcp: DiagnosticsMCPResponse = Field(default_factory=DiagnosticsMCPResponse)
    database: DiagnosticsDatabaseResponse = Field(default_factory=DiagnosticsDatabaseResponse)
    workers: DiagnosticsWorkersResponse = Field(default_factory=DiagnosticsWorkersResponse)
    prompt_cache: DiagnosticsPromptCacheResponse = Field(default_factory=DiagnosticsPromptCacheResponse)
    task_runtime: DiagnosticsTaskRuntimeResponse = Field(default_factory=DiagnosticsTaskRuntimeResponse)
    store_context: DiagnosticsStoreContextResponse = Field(default_factory=DiagnosticsStoreContextResponse)
    active_jobs: DiagnosticsActiveJobsResponse = Field(default_factory=DiagnosticsActiveJobsResponse)


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
    skill_slug: str = ""


class BatchFeedbackCountsResponse(BaseModel):
    total: int = 0
    processed: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    retried: int = 0
    remaining: int = 0


class BatchFeedbackItemResponse(BaseModel):
    product_id: str = ""
    product_name: str = ""
    item_status: str = ""
    reason_code: Optional[str] = None
    user_message: Optional[str] = None
    at: Optional[str] = None


class BatchFeedbackEventResponse(BaseModel):
    sequence: int = 0
    type: str = ""
    stage: str = ""
    label: str = ""
    message: str = ""
    at: Optional[str] = None
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    item_status: Optional[str] = None
    reason_code: Optional[str] = None
    user_message: Optional[str] = None
    retryable: Optional[bool] = None


class BatchFeedbackResponse(BaseModel):
    stage: str = ""
    stage_label: str = ""
    status_message: str = ""
    sequence: int = 0
    warning_count: int = 0
    eta_seconds: Optional[int] = None
    last_event_at: Optional[str] = None
    stalled_since: Optional[str] = None
    heartbeat_at: Optional[str] = None
    summary_counts: BatchFeedbackCountsResponse = Field(default_factory=BatchFeedbackCountsResponse)
    current_item: Optional[BatchFeedbackItemResponse] = None
    last_completed_item: Optional[BatchFeedbackItemResponse] = None
    latest_event: Optional[BatchFeedbackEventResponse] = None
    recent_events: list[BatchFeedbackEventResponse] = Field(default_factory=list)
    next_action_hints: list[str] = Field(default_factory=list)


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
    feedback: BatchFeedbackResponse = Field(default_factory=BatchFeedbackResponse)


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

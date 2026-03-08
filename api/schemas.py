"""API request/response schemas — thin wrappers over core models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from core.models import Product, SeoScore, SeoSuggestion


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


# ── SEO ──────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list)


class ScoreResponse(BaseModel):
    product_id: str
    score: SeoScore


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


class RewriteResponse(BaseModel):
    suggestion: Optional[SeoSuggestion] = None
    field_value: str = ""
    thinking_text: str = ""


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
    ai_thinking_mode: bool = False
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


class ProviderHealthResponse(BaseModel):
    status: str
    message: str


class TestConnectionResponse(BaseModel):
    ok: bool
    ikas_ok: bool = False
    message: str = ""


class ProviderModelsResponse(BaseModel):
    models: list[str]


# ── MCP ──────────────────────────────────────────────────────────────────────

class MCPStatusResponse(BaseModel):
    has_token: bool = False
    initialized: bool = False
    tool_count: int = 0
    message: str = ""


class ChatMessageSchema(BaseModel):
    role: str
    content: str
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    thinking: str = ""
    error: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)

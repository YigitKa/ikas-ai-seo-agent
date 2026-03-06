from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str
    name: str
    description: str = ""
    description_translations: dict[str, str] = Field(default_factory=dict)
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    price: Optional[float] = None
    sku: Optional[str] = None
    status: str = "active"


class SeoScore(BaseModel):
    product_id: str
    total_score: int = Field(ge=0, le=100)
    title_score: int = Field(ge=0, le=25)
    description_score: int = Field(ge=0, le=30)
    english_description_score: int = Field(ge=0, le=10, default=0)
    meta_score: int = Field(ge=0, le=20)
    meta_desc_score: int = Field(ge=0, le=15)
    keyword_score: int = Field(ge=0, le=10)
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)

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
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)


class AppConfig(BaseModel):
    ikas_store_name: str = ""
    ikas_client_id: str = ""
    ikas_client_secret: str = ""
    ikas_api_url: str = ""
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

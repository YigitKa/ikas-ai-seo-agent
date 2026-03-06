from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Product(BaseModel):
    id: str
    name: str
    description: str = ""
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
    anthropic_api_key: str = ""
    store_language: str = "tr"
    seo_target_keywords: List[str] = Field(default_factory=list)
    dry_run: bool = True
    log_level: str = "INFO"

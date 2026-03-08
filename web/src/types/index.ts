export interface Product {
  id: string;
  name: string;
  description: string;
  description_translations: Record<string, string>;
  meta_title: string | null;
  meta_description: string | null;
  tags: string[];
  category: string | null;
  price: number | null;
  sku: string | null;
  status: string;
  image_url: string | null;
  image_urls: string[];
}

export interface SeoScore {
  product_id: string;
  total_score: number;
  title_score: number;
  description_score: number;
  english_description_score: number;
  meta_score: number;
  meta_desc_score: number;
  keyword_score: number;
  content_quality_score: number;
  technical_seo_score: number;
  readability_score: number;
  issues: string[];
  suggestions: string[];
}

export interface SeoSuggestion {
  product_id: string;
  original_name: string;
  suggested_name: string | null;
  original_description: string;
  suggested_description: string;
  original_description_en: string;
  suggested_description_en: string;
  original_meta_title: string | null;
  suggested_meta_title: string;
  original_meta_description: string | null;
  suggested_meta_description: string;
  thinking_text: string;
  status: string;
  created_at: string;
}

export interface ProductWithScore {
  product: Product;
  score: SeoScore | null;
}

export interface ProductListResponse {
  items: ProductWithScore[];
  total_count: number;
  page: number;
  limit: number;
}

export interface SettingsData {
  store_name: string;
  client_id: string;
  client_secret: string;
  ai_provider: string;
  ai_api_key: string;
  ai_base_url: string;
  ai_model_name: string;
  ai_temperature: number;
  ai_max_tokens: number;
  ai_thinking_mode: boolean;
  languages: string;
  keywords: string;
  dry_run: boolean;
}

export interface ProviderInfo {
  key: string;
  label: string;
}

export interface ProviderHealth {
  status: string;
  message: string;
}

export interface RewriteResponse {
  suggestion: SeoSuggestion | null;
  field_value: string;
  thinking_text: string;
}

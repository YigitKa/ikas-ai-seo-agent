export interface Product {
  id: string;
  name: string;
  slug: string | null;
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
  mcp_token: string;
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

export interface PromptTemplate {
  key: string;
  title: string;
  description: string;
  variables: string[];
  height: number;
  content: string;
}

export interface PromptGroup {
  label: string;
  prompts: PromptTemplate[];
}

export interface RewriteResponse {
  suggestion: SeoSuggestion | null;
  field_value: string;
  thinking_text: string;
}

export interface MCPStatus {
  has_token: boolean;
  initialized: boolean;
  tool_count: number;
  message: string;
  tools: MCPToolInfo[];
}

export interface MCPToolInfo {
  name: string;
  description: string;
}

export interface ToolResult {
  tool: string;
  arguments: Record<string, unknown>;
  result: string;
}

export interface ChatResponseMeta extends Record<string, unknown> {
  model?: string;
  finish_reason?: string;
  stop_reason?: string;
  source?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  elapsed_seconds?: number;
  tokens_per_second?: number;
  time_to_first_token_seconds?: number;
  reasoning_output_tokens?: number;
  context_length?: number;
  context_used_percent?: number;
  context_remaining_percent?: number;
}

export interface LMStudioModelStatus {
  id: string;
  display_name: string;
  status: string;
  context_length: number | null;
}

export interface LMStudioDownloadStatus {
  job_id: string;
  status: 'downloading' | 'paused' | 'completed' | 'failed' | string;
  bytes_per_second: number | null;
  estimated_completion: string;
  completed_at: string;
  total_size_bytes: number | null;
  downloaded_bytes: number | null;
  started_at: string;
}

export interface LMStudioLiveStatus {
  provider: string;
  configured_model: string;
  selected_model: LMStudioModelStatus;
  models: LMStudioModelStatus[];
  download_status: LMStudioDownloadStatus | null;
}

export interface SuggestionSavedInfo {
  product_id: string;
  product_name: string;
  fields: Record<string, string>;
}

export interface ChatWsMessage {
  type: 'response' | 'error' | 'thinking' | 'mcp_status' | 'context_set' | 'cleared' | 'cancelled';
  content?: string;
  thinking?: string;
  tool_results?: ToolResult[];
  error?: boolean;
  meta?: ChatResponseMeta;
  has_token?: boolean;
  initialized?: boolean;
  tool_count?: number;
  tools?: MCPToolInfo[];
  message?: string;
  product_id?: string;
  product_name?: string;
  suggestion_saved?: SuggestionSavedInfo;
}

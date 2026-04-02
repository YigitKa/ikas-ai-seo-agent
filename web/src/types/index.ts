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
  seo_score: number;
  geo_score: number;
  aeo_score: number;
  title_score: number;
  description_score: number;
  english_description_score: number;
  meta_score: number;
  meta_desc_score: number;
  keyword_score: number;
  content_quality_score: number;
  technical_seo_score: number;
  readability_score: number;
  ai_citability_score: number;
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
  ai_thinking_mode_chat: boolean;
  ai_thinking_mode_batch: boolean;
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
  runtime_variables: string[];
  height: number;
  content: string;
}

export interface PromptGroup {
  label: string;
  prompts: PromptTemplate[];
}

export interface PromptLayer {
  order: number;
  prompt_key: string | null;
  label: string;
  description: string;
  linked_keys: string[];
}

export interface PromptLayeringFlow {
  id: string;
  title: string;
  description: string;
  layers: PromptLayer[];
}

export interface PromptLayeringOrder {
  flows: PromptLayeringFlow[];
}

export interface SkillPromptLayer {
  type: 'inline' | 'prompt_reference' | string;
  label: string;
  prompt_key: string;
  content: string;
}

export interface SkillResolvedPromptLayer {
  type: 'inline' | 'prompt_reference' | string;
  label: string;
  source: string;
  content: string;
}

export interface SkillDefinition {
  schema_version: number;
  slug: string;
  name: string;
  description: string;
  when_to_use: string;
  applies_to: string[];
  allowed_tools: string[];
  prompt_layers: SkillPromptLayer[];
  tags: string[];
  priority: number;
  status: string;
  instructions_markdown: string;
  source: string;
  content_hash: string;
  is_default: boolean;
}

export interface SkillValidation {
  ok: boolean;
  errors: string[];
  warnings: string[];
  resolved_prompt_layers: SkillResolvedPromptLayer[];
}

export interface SkillPreviewDebug {
  applies_to: string;
  tool_scope_mode: string;
  tool_scope_note: string;
  prompt_char_count: number;
  instruction_word_count: number;
  requested_tools: string[];
  resolved_tools: string[];
  flow_tools: string[];
  resolved_layer_count: number;
}

export interface SkillPreview {
  validation: SkillValidation;
  composed_prompt: string;
  debug: SkillPreviewDebug;
}

export interface ActiveSkillSummary {
  slug: string;
  name: string;
  description: string;
  applies_to: string[];
  allowed_tools: string[];
  resolved_tools?: string[];
  status: string;
  source: string;
  selection_mode?: string;
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

export interface ToolResultEnvelopeError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  retryable: boolean;
}

export interface ToolResultEnvelope<T = unknown> {
  ok: boolean;
  tool_name: string;
  data: T | null;
  error: ToolResultEnvelopeError | null;
  meta: Record<string, unknown>;
}

export interface ChatResponseMeta extends Record<string, unknown> {
  model?: string;
  finish_reason?: string;
  stop_reason?: string;
  source?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  estimated_cost?: number;
  session_total_cost?: number;
  elapsed_seconds?: number;
  tokens_per_second?: number;
  time_to_first_token_seconds?: number;
  reasoning_output_tokens?: number;
  context_length?: number;
  context_used_percent?: number;
  context_remaining_percent?: number;
  active_skill?: ActiveSkillSummary | null;
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
  type: 'chunk' | 'thinking_chunk' | 'response_done' | 'response' | 'error' | 'thinking' | 'mcp_status' | 'skill_status' | 'context_set' | 'cleared' | 'cancelled';
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
  pending_suggestion?: SeoSuggestion | null;
  active_skill?: ActiveSkillSummary | null;
}

export interface LlmsJob {
  id: string;
  task_id: string | null;
  status: string;
  total_count: number;
  processed_count: number;
  failed_count: number;
  skipped_count: number;
  created_at: string;
  updated_at: string;
  last_error?: string | null;
  options?: Record<string, unknown>;
}

export interface LlmsEntrySummary {
  product_id: string;
  product_name: string;
  category: string | null;
  summary: string;
  status: string;
  updated_at: string;
}

export interface TaskErrorInfo {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface TaskRecord {
  id: string;
  type: string;
  status: string;
  progress: number;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  error: TaskErrorInfo | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
}

export interface LlmsStatus {
  job: LlmsJob | null;
  counts: {
    total_products: number;
    processed: number;
    pending: number;
    failed: number;
    unprocessed: number;
  };
  current: {
    product_id: string;
    product_name: string;
    category: string | null;
  } | null;
  latest_processed: LlmsEntrySummary[];
  unprocessed: {
    product_id: string;
    product_name: string;
    category: string | null;
  }[];
}

// ── Batch Operations ──────────────────────────────────────────────────────────

export interface BatchConfig {
  score_threshold: number;
  category_filter: string;
  in_stock_only: boolean;
  preserve_specs: boolean;
  prevent_cannibalization: boolean;
  max_title_change_pct: number;
  target_fields: string[];
  skill_slug: string;
}

export type BatchJobStatus =
  | 'idle'
  | 'analyzing'
  | 'analyzed'
  | 'running'
  | 'paused'
  | 'completed'
  | 'completed_with_errors'
  | 'failed'
  | 'cancelled';

export interface BatchJob {
  id: string;
  task_id: string | null;
  status: BatchJobStatus;
  config: BatchConfig;
  total_count: number;
  processed_count: number;
  skipped_count: number;
  failed_count: number;
  avg_score_before: number;
  avg_score_after: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error: string | null;
}

export type BatchItemStatus =
  | 'pending'
  | 'analyzed'
  | 'processing'
  | 'approved'
  | 'rejected'
  | 'applied'
  | 'skipped'
  | 'failed'
  | 'rolled_back';

export interface BatchItem {
  id: number;
  job_id: string;
  product_id: string;
  product_name: string;
  status: BatchItemStatus;
  score_before: number | null;
  score_after: number | null;
  skip_reason: string | null;
  has_rollback: boolean;
  suggestion_data: Record<string, unknown> | null;
}

export interface BatchJobDetail {
  job: BatchJob;
  items: BatchItem[];
}

export interface BatchStats {
  total_jobs: number;
  total_processed: number;
  avg_score_improvement: number;
  active_job: BatchJob | null;
}

// ── Reports / Daily Tracking ────────────────────────────────────────────────

export interface DailyStoreTrend {
  snapshot_date: string;
  product_count: number;
  avg_total: number;
  avg_seo: number;
  avg_geo: number;
  avg_aeo: number;
  avg_title: number;
  avg_description: number;
  avg_english_description: number;
  avg_meta: number;
  avg_meta_desc: number;
  avg_keyword: number;
  avg_content_quality: number;
  avg_technical_seo: number;
  avg_readability: number;
  avg_ai_citability: number;
  avg_issues: number;
}

export interface DailyProductTrend {
  snapshot_date: string;
  total_score: number;
  seo_score: number;
  geo_score: number;
  aeo_score: number;
  title_score: number;
  description_score: number;
  english_description_score: number;
  meta_score: number;
  meta_desc_score: number;
  keyword_score: number;
  content_quality_score: number;
  technical_seo_score: number;
  readability_score: number;
  ai_citability_score: number;
  issues_count: number;
}

export interface ReportSummary {
  first_date: string | null;
  latest_date: string | null;
  days_tracked: number;
  total_products: number;
  snapshot_count: number;
  first_avg: Record<string, number>;
  latest_avg: Record<string, number>;
  improvement: Record<string, number>;
}

export interface TopImprover {
  product_id: string;
  product_name: string;
  first_score: number;
  latest_score: number;
  delta: number;
}

export interface ScoreChangeLogEntry {
  id: number;
  product_id: string;
  product_name: string;
  operation: string;
  score_before: number | null;
  score_after: number | null;
  delta: number | null;
  job_id: string | null;
  created_at: string;
}

export interface ScoreChangeSummary {
  total_events: number;
  unique_products: number;
  avg_delta: number | null;
  improved_count: number;
  degraded_count: number;
  unchanged_count: number;
  best_delta: number | null;
  worst_delta: number | null;
  total_gain: number;
  net_change: number;
  avg_score_after: number | null;
}

export interface HourlyActivity {
  hour: string;
  event_count: number;
  avg_delta: number | null;
  improved: number;
  degraded: number;
}

export interface DailyActivity {
  day: string;
  event_count: number;
  avg_delta: number | null;
  improved: number;
  degraded: number;
  unique_products: number;
}

export interface ScoreDistributionBucket {
  bucket: string;
  count: number;
}

export interface OperationMetric {
  operation: string;
  total: number;
  avg_delta: number | null;
  success_rate: number | null;
  best_delta: number | null;
  worst_delta: number | null;
  avg_score_after: number | null;
}

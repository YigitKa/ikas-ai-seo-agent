const BASE = '';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers as Record<string, string> },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Products ────────────────────────────────────────────────────────────────

import type {
  ProductListResponse,
  ProductWithScore,
  PromptGroup,
  PromptLayeringOrder,
  SkillDefinition,
  SkillPreview,
  SkillValidation,
  LMStudioLiveStatus,
  SettingsData,
  ProviderInfo,
  ProviderHealth,
  RewriteResponse,
  SeoSuggestion,
  SeoScore,
  MCPStatus,
  LlmsStatus,
  LlmsJob,
  LlmsEntrySummary,
  TaskRecord,
  BatchConfig,
  BatchJob,
  BatchJobDetail,
  BatchItem,
  BatchStats,
  DailyStoreTrend,
  DailyProductTrend,
  ReportSummary,
  TopImprover,
} from '../types';

export async function fetchProducts(
  page = 1,
  limit = 50,
  filter = 'all',
  options: {
    search?: string;
    category?: string;
    score_threshold?: number;
    title_score_threshold?: number;
    description_score_threshold?: number;
    english_description_score_threshold?: number;
    meta_score_threshold?: number;
    meta_desc_score_threshold?: number;
    sort_by?: string;
    sort_dir?: 'asc' | 'desc';
  } = {},
): Promise<ProductListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
    filter,
  });
  if (options.search?.trim()) params.set('search', options.search.trim());
  if (options.category?.trim()) params.set('category', options.category.trim());
  if (typeof options.score_threshold === 'number') params.set('score_threshold', String(options.score_threshold));
  if (typeof options.title_score_threshold === 'number') params.set('title_score_threshold', String(options.title_score_threshold));
  if (typeof options.description_score_threshold === 'number') params.set('description_score_threshold', String(options.description_score_threshold));
  if (typeof options.english_description_score_threshold === 'number') params.set('english_description_score_threshold', String(options.english_description_score_threshold));
  if (typeof options.meta_score_threshold === 'number') params.set('meta_score_threshold', String(options.meta_score_threshold));
  if (typeof options.meta_desc_score_threshold === 'number') params.set('meta_desc_score_threshold', String(options.meta_desc_score_threshold));
  if (options.sort_by?.trim()) params.set('sort_by', options.sort_by.trim());
  if (options.sort_dir) params.set('sort_dir', options.sort_dir);
  return request(`/api/products?${params.toString()}`);
}

export async function fetchProductsFromIkas(
  page = 1,
  limit = 50,
): Promise<ProductListResponse> {
  return request('/api/products/fetch', {
    method: 'POST',
    body: JSON.stringify({ page, limit }),
  });
}

export async function getProduct(id: string): Promise<ProductWithScore> {
  return request(`/api/products/${id}`);
}

// ── SEO ─────────────────────────────────────────────────────────────────────

export async function generateLlmsTxt(): Promise<string> {
  const res = await fetch('/api/seo/generate-llms-txt');
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.text();
}

// ── llms.txt pipeline ─────────────────────────────────────────────────────────

export async function getLlmsStatus(): Promise<LlmsStatus> {
  return request('/api/llms/status');
}

export async function startLlmsJob(): Promise<{ job: LlmsJob }> {
  return request('/api/llms/start', { method: 'POST' });
}

export async function pauseLlmsJob(): Promise<{ message: string }> {
  return request('/api/llms/pause', { method: 'POST' });
}

export async function resumeLlmsJob(): Promise<{ job: LlmsJob }> {
  return request('/api/llms/resume', { method: 'POST' });
}

export async function stopLlmsJob(): Promise<{ message: string }> {
  return request('/api/llms/stop', { method: 'POST' });
}

export async function listLlmsProcessed(limit?: number): Promise<{ items: LlmsEntrySummary[] }> {
  const params = typeof limit === 'number' ? `?limit=${limit}` : '';
  return request(`/api/llms/processed${params}`);
}

export async function listLlmsPending(limit?: number): Promise<{ items: LlmsEntrySummary[] }> {
  const params = typeof limit === 'number' ? `?limit=${limit}` : '';
  return request(`/api/llms/pending${params}`);
}

export async function regenerateLlmsSummary(productId: string): Promise<{ item: LlmsEntrySummary }> {
  return request(`/api/llms/regenerate/${productId}`, { method: 'POST' });
}

export async function analyzeAll(): Promise<{ message: string }> {
  return request('/api/seo/analyze', { method: 'POST' });
}

export async function analyzeProduct(id: string): Promise<{ product_id: string; score: SeoScore }> {
  return request(`/api/seo/analyze/${id}`, { method: 'POST' });
}

export async function getScore(id: string): Promise<{ product_id: string; score: SeoScore }> {
  return request(`/api/seo/scores/${id}`);
}

// ── Suggestions ─────────────────────────────────────────────────────────────

export async function generateSuggestion(productId: string): Promise<RewriteResponse> {
  return request(`/api/suggestions/generate/${productId}`, { method: 'POST' });
}

export async function generateFieldRewrite(
  productId: string,
  field: string,
): Promise<RewriteResponse> {
  return request(`/api/suggestions/generate-field/${productId}`, {
    method: 'POST',
    body: JSON.stringify({ product_id: productId, field }),
  });
}

export async function getSuggestions(productId: string): Promise<SeoSuggestion[]> {
  return request(`/api/suggestions/${productId}`);
}

export async function approveSuggestion(productId: string): Promise<{ message: string }> {
  return request(`/api/suggestions/${productId}/approve`, { method: 'PATCH' });
}

export async function rejectSuggestion(productId: string): Promise<{ message: string }> {
  return request(`/api/suggestions/${productId}/reject`, { method: 'PATCH' });
}

export async function applyApproved(): Promise<{ applied: number; total: number }> {
  return request('/api/suggestions/apply', { method: 'POST' });
}

// ── Settings ────────────────────────────────────────────────────────────────

export async function getSettings(): Promise<SettingsData> {
  return request('/api/settings');
}

export async function updateSettings(values: Record<string, unknown>): Promise<{ message: string }> {
  return request('/api/settings', {
    method: 'PUT',
    body: JSON.stringify({ values }),
  });
}

export async function syncProductsFromIkas(): Promise<{ fetched_count: number; total_count: number }> {
  return request('/api/products/sync', {
    method: 'POST',
  });
}

export async function resetLocalProductData(): Promise<{
  message: string;
  products_deleted: number;
  scores_deleted: number;
  suggestions_deleted: number;
  logs_deleted: number;
}> {
  return request('/api/products/reset', {
    method: 'POST',
  });
}

export async function getPromptTemplates(): Promise<{ groups: PromptGroup[] }> {
  return request('/api/settings/prompts');
}

export async function savePromptTemplates(
  templates: Record<string, string>,
): Promise<{ message: string }> {
  return request('/api/settings/prompts', {
    method: 'PUT',
    body: JSON.stringify({ templates }),
  });
}

export async function resetPromptTemplates(
  promptKeys: string[] = [],
): Promise<{ groups: PromptGroup[] }> {
  return request('/api/settings/prompts/reset', {
    method: 'POST',
    body: JSON.stringify({ prompt_keys: promptKeys }),
  });
}

export async function getPromptLayeringOrder(): Promise<PromptLayeringOrder> {
  return request('/api/settings/prompts/layering');
}

export async function getSkills(): Promise<{ items: SkillDefinition[]; available_tools: string[] }> {
  return request('/api/settings/skills');
}

export async function getSkill(slug: string): Promise<SkillDefinition> {
  return request(`/api/settings/skills/item/${encodeURIComponent(slug)}`);
}

export async function saveSkill(
  slug: string,
  skill: SkillDefinition,
): Promise<SkillDefinition> {
  return request(`/api/settings/skills/item/${encodeURIComponent(slug)}`, {
    method: 'PUT',
    body: JSON.stringify({ skill }),
  });
}

export async function resetSkill(slug: string): Promise<SkillDefinition> {
  return request(`/api/settings/skills/item/${encodeURIComponent(slug)}/reset`, {
    method: 'POST',
  });
}

export async function deleteSkill(slug: string): Promise<{ message: string; ok: boolean }> {
  return request(`/api/settings/skills/item/${encodeURIComponent(slug)}`, {
    method: 'DELETE',
  });
}

export async function validateSkill(skill: SkillDefinition): Promise<SkillValidation> {
  return request('/api/settings/skills/validate', {
    method: 'POST',
    body: JSON.stringify({ skill }),
  });
}

export async function previewSkill(
  skill: SkillDefinition,
  appliesTo = 'chat',
): Promise<SkillPreview> {
  const suffix = appliesTo ? `?applies_to=${encodeURIComponent(appliesTo)}` : '';
  return request(`/api/settings/skills/preview${suffix}`, {
    method: 'POST',
    body: JSON.stringify({ skill }),
  });
}

export async function exportSkill(slug: string): Promise<SkillDefinition> {
  return request(`/api/settings/skills/item/${encodeURIComponent(slug)}/export`);
}

export async function importSkill(skill: SkillDefinition): Promise<SkillDefinition> {
  return request('/api/settings/skills/import', {
    method: 'POST',
    body: JSON.stringify({ skill }),
  });
}

export async function getProviders(): Promise<{ providers: ProviderInfo[] }> {
  return request('/api/settings/providers');
}

export async function getProviderHealth(): Promise<ProviderHealth> {
  return request('/api/settings/health');
}

export async function getProviderModels(
  provider: string,
  baseUrl = '',
): Promise<{ models: string[] }> {
  const params = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : '';
  return request(`/api/settings/models/${provider}${params}`);
}

export async function getLmStudioLiveStatus(jobId = ''): Promise<LMStudioLiveStatus> {
  const params = jobId ? `?job_id=${encodeURIComponent(jobId)}` : '';
  return request(`/api/settings/lm-studio/status${params}`);
}

export async function testConnection(values: Record<string, unknown>): Promise<{
  ok: boolean;
  ikas_ok: boolean;
  message: string;
}> {
  return request('/api/settings/test-connection', {
    method: 'POST',
    body: JSON.stringify({ values }),
  });
}

// ── MCP ─────────────────────────────────────────────────────────────────────

export async function getMcpStatus(): Promise<MCPStatus> {
  return request('/api/mcp/status');
}

export async function initializeMcp(): Promise<MCPStatus> {
  return request('/api/mcp/initialize', { method: 'POST' });
}

export async function clearChat(): Promise<{ message: string }> {
  return request('/api/chat/clear', { method: 'POST' });
}

// ── Batch Operations ─────────────────────────────────────────────────────────

export async function listTasks(params: {
  type?: string[];
  status?: string[];
  limit?: number;
  offset?: number;
} = {}): Promise<{ items: TaskRecord[] }> {
  const qs = new URLSearchParams();
  for (const taskType of params.type ?? []) qs.append('type', taskType);
  for (const status of params.status ?? []) qs.append('status', status);
  if (typeof params.limit === 'number') qs.set('limit', String(params.limit));
  if (typeof params.offset === 'number') qs.set('offset', String(params.offset));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return request(`/api/tasks${suffix}`);
}

export async function getTask(taskId: string): Promise<TaskRecord> {
  return request(`/api/tasks/${taskId}`);
}

export async function resumeTask(taskId: string): Promise<TaskRecord> {
  return request(`/api/tasks/${taskId}/resume`, { method: 'POST' });
}

export async function retryTask(taskId: string): Promise<TaskRecord> {
  return request(`/api/tasks/${taskId}/retry`, { method: 'POST' });
}

export async function stopTask(taskId: string): Promise<TaskRecord> {
  return request(`/api/tasks/${taskId}/stop`, { method: 'POST' });
}

export async function cancelTask(taskId: string): Promise<TaskRecord> {
  return request(`/api/tasks/${taskId}/cancel`, { method: 'POST' });
}

export async function getBatchStats(): Promise<BatchStats> {
  return request('/api/batch/stats');
}

export async function listBatchJobs(): Promise<BatchJob[]> {
  return request('/api/batch/jobs');
}

export async function getBatchJob(jobId: string): Promise<BatchJobDetail> {
  return request(`/api/batch/jobs/${jobId}`);
}

export async function startBatchJob(
  config: BatchConfig,
  productIds: string[],
): Promise<BatchJob> {
  return request('/api/batch/jobs', {
    method: 'POST',
    body: JSON.stringify({ config, product_ids: productIds }),
  });
}

export async function applyBatchJob(jobId: string): Promise<BatchJob> {
  return request(`/api/batch/jobs/${jobId}/apply`, { method: 'POST' });
}

export async function stopBatchJob(jobId: string): Promise<BatchJob> {
  return request(`/api/batch/jobs/${jobId}/stop`, { method: 'POST' });
}

export async function rollbackBatchJob(jobId: string): Promise<{ rolled_back: number; total: number }> {
  return request(`/api/batch/jobs/${jobId}/rollback`, { method: 'POST' });
}

export async function rollbackBatchItem(itemId: number): Promise<{ ok: boolean; product_id: string }> {
  return request(`/api/batch/items/${itemId}/rollback`, { method: 'POST' });
}

export async function updateBatchItem(
  itemId: number,
  decision: 'approved' | 'rejected' | 'revised',
  revisedData?: Record<string, unknown>,
): Promise<BatchItem> {
  return request(`/api/batch/items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify({ decision, revised_data: revisedData }),
  });
}

export async function bulkUpdateBatchItems(
  itemIds: number[],
  decision: 'approved' | 'rejected',
): Promise<{ updated: number }> {
  return request('/api/batch/items/bulk-decision', {
    method: 'POST',
    body: JSON.stringify({ item_ids: itemIds, decision }),
  });
}

export async function regenerateBatchItem(itemId: number): Promise<BatchItem> {
  return request(`/api/batch/items/${itemId}/regenerate`, { method: 'POST' });
}

export async function regenerateBatchItemField(itemId: number, fieldKey: string): Promise<BatchItem> {
  return request(`/api/batch/items/${itemId}/fields/${fieldKey}/regenerate`, { method: 'POST' });
}

export function createBatchJobStream(jobId: string): EventSource {
  return new EventSource(`/api/batch/jobs/${jobId}/stream`);
}

export async function deleteBatchJob(jobId: string): Promise<{ ok: boolean }> {
  return request(`/api/batch/jobs/${jobId}`, { method: 'DELETE' });
}

export async function getCategories(): Promise<string[]> {
  return request('/api/products/categories');
}

// ── Reports / Daily Tracking ────────────────────────────────────────────────

export async function getStoreTrends(days = 90): Promise<DailyStoreTrend[]> {
  return request(`/api/reports/store-trends?days=${days}`);
}

export async function getProductTrends(productId: string, days = 90): Promise<DailyProductTrend[]> {
  return request(`/api/reports/product-trends/${productId}?days=${days}`);
}

export async function getReportSummary(): Promise<ReportSummary> {
  return request('/api/reports/summary');
}

export async function getTopImprovers(limit = 10): Promise<TopImprover[]> {
  return request(`/api/reports/top-improvers?limit=${limit}`);
}

export async function takeSnapshot(): Promise<{ message: string }> {
  return request('/api/reports/take-snapshot', { method: 'POST' });
}

export async function getScoreChangeLog(params: {
  start_date?: string;
  end_date?: string;
  product_id?: string;
  operation?: string;
  job_id?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<import('../types').ScoreChangeLogEntry[]> {
  const qs = new URLSearchParams();
  if (params.start_date) qs.set('start_date', params.start_date);
  if (params.end_date) qs.set('end_date', params.end_date);
  if (params.product_id) qs.set('product_id', params.product_id);
  if (params.operation) qs.set('operation', params.operation);
  if (params.job_id) qs.set('job_id', params.job_id);
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.offset) qs.set('offset', String(params.offset));
  return request(`/api/reports/score-change-log?${qs.toString()}`);
}

export async function getScoreChangeSummary(params: {
  start_date?: string;
  end_date?: string;
} = {}): Promise<import('../types').ScoreChangeSummary> {
  const qs = new URLSearchParams();
  if (params.start_date) qs.set('start_date', params.start_date);
  if (params.end_date) qs.set('end_date', params.end_date);
  return request(`/api/reports/score-change-summary?${qs.toString()}`);
}

export async function getHourlyActivity(params: {
  start_date?: string;
  end_date?: string;
} = {}): Promise<import('../types').HourlyActivity[]> {
  const qs = new URLSearchParams();
  if (params.start_date) qs.set('start_date', params.start_date);
  if (params.end_date) qs.set('end_date', params.end_date);
  return request(`/api/reports/hourly-activity?${qs.toString()}`);
}

export async function getDailyActivity(params: {
  start_date?: string;
  end_date?: string;
} = {}): Promise<import('../types').DailyActivity[]> {
  const qs = new URLSearchParams();
  if (params.start_date) qs.set('start_date', params.start_date);
  if (params.end_date) qs.set('end_date', params.end_date);
  return request(`/api/reports/daily-activity?${qs.toString()}`);
}

export async function getScoreDistribution(): Promise<import('../types').ScoreDistributionBucket[]> {
  return request('/api/reports/score-distribution');
}

export async function getOperationMetrics(params: {
  start_date?: string;
  end_date?: string;
} = {}): Promise<import('../types').OperationMetric[]> {
  const qs = new URLSearchParams();
  if (params.start_date) qs.set('start_date', params.start_date);
  if (params.end_date) qs.set('end_date', params.end_date);
  return request(`/api/reports/operation-metrics?${qs.toString()}`);
}

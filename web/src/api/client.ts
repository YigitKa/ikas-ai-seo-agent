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
  LMStudioLiveStatus,
  SettingsData,
  ProviderInfo,
  ProviderHealth,
  RewriteResponse,
  SeoSuggestion,
  SeoScore,
  MCPStatus,
} from '../types';

export async function fetchProducts(
  page = 1,
  limit = 50,
  filter = 'all',
): Promise<ProductListResponse> {
  return request(`/api/products?page=${page}&limit=${limit}&filter=${filter}`);
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

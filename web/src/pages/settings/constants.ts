import type { BannerTone } from '../../components/settings/UiPrimitives';

export type ProviderMeta = {
  summary: string;
  apiKeyLabel?: string;
  apiKeyPlaceholder?: string;
  baseUrlLabel?: string;
  baseUrlPlaceholder?: string;
  defaultBaseUrl?: string;
  lockedBaseUrl?: string;
  modelHint: string;
};

export const PROVIDER_META: Record<string, ProviderMeta> = {
  none: {
    summary: 'AI yeniden yazma kapali. Sadece SEO analizi calisir.',
    modelHint: 'Model secimi gerekmiyor.',
  },
  anthropic: {
    summary: 'Claude modelleri ile urun rewrite ve ceviri uretir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'sk-ant-...',
    modelHint: 'Hazir Claude modellerinden birini secin.',
  },
  openai: {
    summary: 'OpenAI Responses/Chat uyumlu endpoint kullanir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'sk-...',
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://api.openai.com/v1',
    defaultBaseUrl: 'https://api.openai.com/v1',
    modelHint: 'Hazir GPT modelleri listelenir.',
  },
  gemini: {
    summary: 'Google Gemini API ile rewrite ve translation calisir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'AIza...',
    modelHint: 'Gemini modelini secin.',
  },
  openrouter: {
    summary: 'OpenRouter ile tek API key uzerinden farkli saglayicilari kullanir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'sk-or-...',
    baseUrlLabel: 'Base URL',
    lockedBaseUrl: 'https://openrouter.ai/api/v1',
    modelHint: 'Saglayici/model formatinda model secin.',
  },
  ollama: {
    summary: 'Yerel Ollama instance uzerinden calisir. Model listesini tarayabilirsiniz.',
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'http://localhost:11434/v1',
    defaultBaseUrl: 'http://localhost:11434/v1',
    modelHint: 'Kurulu modelleri tarayin ya da elle model girin.',
  },
  'lm-studio': {
    summary: 'Yerel LM Studio OpenAI-compatible endpoint kullanir.',
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'http://localhost:1234/v1',
    defaultBaseUrl: 'http://localhost:1234/v1',
    modelHint: 'Yuklu modelleri tarayin ya da elle model girin.',
  },
  custom: {
    summary: 'OpenAI-compatible herhangi bir endpoint ile calisir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'Opsiyonel',
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://your-endpoint.example/v1',
    modelHint: 'Model adini manuel girin.',
  },
};

export const PRESET_MODELS: Record<string, string[]> = {
  anthropic: [
    'claude-haiku-4-5-20251001',
    'claude-sonnet-4-5-20250514',
    'claude-opus-4-5-20250514',
    'claude-haiku-3-5-20241022',
  ],
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  gemini: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash'],
  openrouter: [
    'openai/gpt-4o-mini',
    'openai/gpt-4o',
    'anthropic/claude-3-haiku',
    'anthropic/claude-3-sonnet',
    'google/gemini-flash-1.5',
    'meta-llama/llama-3-8b-instruct',
  ],
};

export const DISCOVERABLE_PROVIDERS = new Set(['ollama', 'lm-studio']);

export function buildModelOptions(provider: string, currentModel: string, discovered: string[]) {
  return uniqueStrings([currentModel, ...discovered, ...(PRESET_MODELS[provider] ?? [])]);
}

export function uniqueStrings(values: string[]) {
  const seen = new Set<string>();
  const items: string[] = [];
  for (const value of values) {
    const normalized = value.trim();
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    items.push(normalized);
  }
  return items;
}

export function toneFromHealth(status?: string): BannerTone {
  if (status === 'ok') {
    return 'success';
  }
  if (status === 'error' || status === 'offline' || status === 'missing_url') {
    return 'error';
  }
  return 'info';
}

export function formatBytes(value: number) {
  if (value >= 1024 ** 3) {
    return `${(value / 1024 ** 3).toFixed(2)} GB`;
  }
  if (value >= 1024 ** 2) {
    return `${(value / 1024 ** 2).toFixed(2)} MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${value} B`;
}

export function formatByteProgress(downloaded?: number | null, total?: number | null) {
  if (typeof downloaded !== 'number' || typeof total !== 'number' || total <= 0) {
    return 'Bilinmiyor';
  }
  const percent = ((downloaded / total) * 100).toFixed(1);
  return `${formatBytes(downloaded)} / ${formatBytes(total)} (${percent}%)`;
}

export function formatIsoDateTime(value?: string) {
  if (!value) {
    return 'Bilinmiyor';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('tr-TR');
}

export function flattenPromptValues(groups: { prompts: { key: string; content: string }[] }[]) {
  const values: Record<string, string> = {};
  for (const group of groups) {
    for (const prompt of group.prompts) {
      values[prompt.key] = prompt.content;
    }
  }
  return values;
}

export function formatError(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}

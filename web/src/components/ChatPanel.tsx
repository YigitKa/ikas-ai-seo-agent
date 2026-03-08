import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getLmStudioLiveStatus, getSettings } from '../api/client';
import { useChat, type ChatMessage } from '../hooks/useChat';
import type { ChatResponseMeta, Product, SeoScore, SuggestionSavedInfo, ToolResult } from '../types';

interface Props {
  productId?: string;
  productName?: string;
  productCategory?: string | null;
  seoScore?: number | null;
  product?: Product | null;
  score?: SeoScore | null;
}

interface PromptParamOption {
  key: string;
  label: string;
  description: string;
  value: string;
  preview: string;
  searchText: string;
}

interface ParamTriggerState {
  start: number;
  end: number;
  query: string;
}

interface StarterPrompt {
  label: string;
  template: string;
}

function stripHtml(value: string) {
  return value
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<\/li>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\r/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}

function compactPreview(value: string, maxLength = 120) {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 1)}...`;
}

function createPromptParamOption(
  key: string,
  label: string,
  description: string,
  rawValue: string | null | undefined,
) {
  const normalizedValue = (rawValue ?? '').trim() || 'Belirtilmemis';
  return {
    key,
    label,
    description,
    value: normalizedValue,
    preview: compactPreview(normalizedValue),
    searchText: `${key} ${label} ${description}`.toLowerCase(),
  } satisfies PromptParamOption;
}

function buildSeoMetricsSummary(score?: SeoScore | null) {
  if (!score) {
    return 'SEO metrikleri henuz okunmadi.';
  }

  const sections = [
    `Toplam SEO skoru: ${score.total_score}/100`,
    `Baslik skoru: ${score.title_score}/15`,
    `Aciklama skoru: ${score.description_score}/20`,
    `Ingilizce aciklama skoru: ${score.english_description_score}/5`,
    `Meta title skoru: ${score.meta_score}/15`,
    `Meta description skoru: ${score.meta_desc_score}/10`,
    `Anahtar kelime skoru: ${score.keyword_score}/10`,
    `Icerik kalitesi skoru: ${score.content_quality_score}/10`,
    `Teknik SEO skoru: ${score.technical_seo_score}/10`,
    `Okunabilirlik skoru: ${score.readability_score}/5`,
  ];

  if (score.issues.length > 0) {
    sections.push(`Sorunlar:\n- ${score.issues.join('\n- ')}`);
  }

  if (score.suggestions.length > 0) {
    sections.push(`Oneriler:\n- ${score.suggestions.join('\n- ')}`);
  }

  return sections.join('\n');
}

function buildPromptParamOptions(product?: Product | null, score?: SeoScore | null) {
  const productDescription = stripHtml(product?.description || '');
  const productDescriptionEn = stripHtml(product?.description_translations?.en || '');
  const seoIssues = score?.issues.length ? `- ${score.issues.join('\n- ')}` : 'Belirtilmemis';
  const seoSuggestions = score?.suggestions.length ? `- ${score.suggestions.join('\n- ')}` : 'Belirtilmemis';

  return [
    createPromptParamOption('productName', 'Urun adi', 'Secili urunun basligi', product?.name),
    createPromptParamOption('productCategory', 'Kategori', 'Secili urunun kategorisi', product?.category),
    createPromptParamOption('productDescription', 'Urun aciklamasi', 'Temizlenmis urun aciklama metni', productDescription),
    createPromptParamOption('productDescriptionEn', 'EN aciklama', 'Varsa Ingilizce aciklama', productDescriptionEn),
    createPromptParamOption('productMetaTitle', 'Meta title', 'Mevcut meta title alani', product?.meta_title),
    createPromptParamOption('productMetaDescription', 'Meta description', 'Mevcut meta description alani', product?.meta_description),
    createPromptParamOption('productTags', 'Etiketler', 'Secili urunun etiketleri', product?.tags.join(', ')),
    createPromptParamOption('productSku', 'SKU', 'Secili urunun SKU degeri', product?.sku),
    createPromptParamOption('productStatus', 'Durum', 'Secili urunun yayindaki durumu', product?.status),
    createPromptParamOption(
      'productPrice',
      'Fiyat',
      'Secili urunun kayitli fiyati',
      typeof product?.price === 'number' ? `${product.price.toFixed(2)} TL` : undefined,
    ),
    createPromptParamOption('seoMetricsSummary', 'SEO ozeti', 'Tum mevcut SEO skor kirilimlari', buildSeoMetricsSummary(score)),
    createPromptParamOption(
      'seoTotalScore',
      'Toplam SEO skoru',
      'Toplam skor',
      typeof score?.total_score === 'number' ? `${score.total_score}/100` : undefined,
    ),
    createPromptParamOption(
      'seoTitleScore',
      'Baslik skoru',
      'Title skor kirilimi',
      typeof score?.title_score === 'number' ? `${score.title_score}/15` : undefined,
    ),
    createPromptParamOption(
      'seoDescriptionScore',
      'Aciklama skoru',
      'Description skor kirilimi',
      typeof score?.description_score === 'number' ? `${score.description_score}/20` : undefined,
    ),
    createPromptParamOption(
      'seoEnglishDescriptionScore',
      'EN aciklama skoru',
      'English description skor kirilimi',
      typeof score?.english_description_score === 'number' ? `${score.english_description_score}/5` : undefined,
    ),
    createPromptParamOption(
      'seoMetaTitleScore',
      'Meta title skoru',
      'Meta title skor kirilimi',
      typeof score?.meta_score === 'number' ? `${score.meta_score}/15` : undefined,
    ),
    createPromptParamOption(
      'seoMetaDescriptionScore',
      'Meta description skoru',
      'Meta description skor kirilimi',
      typeof score?.meta_desc_score === 'number' ? `${score.meta_desc_score}/10` : undefined,
    ),
    createPromptParamOption(
      'seoKeywordScore',
      'Keyword skoru',
      'Anahtar kelime skor kirilimi',
      typeof score?.keyword_score === 'number' ? `${score.keyword_score}/10` : undefined,
    ),
    createPromptParamOption(
      'seoContentQualityScore',
      'Icerik kalitesi skoru',
      'Content quality skor kirilimi',
      typeof score?.content_quality_score === 'number' ? `${score.content_quality_score}/10` : undefined,
    ),
    createPromptParamOption(
      'seoTechnicalScore',
      'Teknik SEO skoru',
      'Technical SEO skor kirilimi',
      typeof score?.technical_seo_score === 'number' ? `${score.technical_seo_score}/10` : undefined,
    ),
    createPromptParamOption(
      'seoReadabilityScore',
      'Okunabilirlik skoru',
      'Readability skor kirilimi',
      typeof score?.readability_score === 'number' ? `${score.readability_score}/5` : undefined,
    ),
    createPromptParamOption('seoIssues', 'SEO sorunlari', 'Mevcut issue listesi', seoIssues),
    createPromptParamOption('seoSuggestions', 'SEO onerileri', 'Mevcut suggestion listesi', seoSuggestions),
  ];
}

function resolvePromptTemplate(template: string, options: PromptParamOption[]) {
  return options.reduce(
    (resolved, option) => resolved.split(`{${option.key}}`).join(option.value),
    template,
  );
}

function getParamTriggerState(value: string, caretPosition: number | null) {
  if (caretPosition === null) {
    return null;
  }

  const textBeforeCaret = value.slice(0, caretPosition);
  const openIndex = textBeforeCaret.lastIndexOf('{');
  if (openIndex === -1) {
    return null;
  }

  if (textBeforeCaret.lastIndexOf('}') > openIndex) {
    return null;
  }

  const query = textBeforeCaret.slice(openIndex + 1);
  if (/\s/.test(query)) {
    return null;
  }

  const closingIndex = value.indexOf('}', openIndex);
  if (closingIndex !== -1 && closingIndex < caretPosition) {
    return null;
  }

  return {
    start: openIndex,
    end: caretPosition,
    query,
  } satisfies ParamTriggerState;
}

function formatDuration(seconds: number) {
  const safeSeconds = Math.max(seconds, 0);
  if (safeSeconds < 60) {
    return safeSeconds < 10 ? `${safeSeconds.toFixed(2)}s` : `${safeSeconds.toFixed(1)}s`;
  }

  const minutes = Math.floor(safeSeconds / 60);
  const remainder = Math.floor(safeSeconds % 60);
  return `${minutes}m ${remainder}s`;
}

function formatCompactNumber(value: number) {
  if (value >= 1000) {
    return value >= 10_000 ? `${Math.round(value / 1000)}K` : `${(value / 1000).toFixed(1)}K`;
  }
  return String(value);
}

function formatThoughtDuration(seconds: number) {
  const safeSeconds = Math.max(seconds, 0);
  if (safeSeconds < 60) {
    return `${safeSeconds.toFixed(2)} seconds`;
  }
  return formatDuration(safeSeconds);
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

function clampPercent(value: number) {
  return Math.min(100, Math.max(0, value));
}

function resolveContextUsage(meta?: ChatResponseMeta, fallbackContextLength?: number | null) {
  const inputTokens = readMetaNumber(meta, 'input_tokens');
  const contextLength = readMetaNumber(meta, 'context_length') ?? fallbackContextLength ?? undefined;
  const usedPercent = readMetaNumber(meta, 'context_used_percent');
  const remainingPercent = readMetaNumber(meta, 'context_remaining_percent');

  if (typeof inputTokens !== 'number' || typeof contextLength !== 'number' || contextLength <= 0) {
    return null;
  }

  const derivedUsed = clampPercent((inputTokens / contextLength) * 100);
  const normalizedUsed = typeof usedPercent === 'number' ? clampPercent(usedPercent) : derivedUsed;
  const normalizedRemaining =
    typeof remainingPercent === 'number'
      ? clampPercent(remainingPercent)
      : clampPercent(100 - normalizedUsed);

  return {
    inputTokens,
    contextLength,
    usedPercent: normalizedUsed,
    remainingPercent: normalizedRemaining,
  };
}

function readMetaNumber(meta: ChatResponseMeta | undefined, key: keyof ChatResponseMeta) {
  const value = meta?.[key];
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

function getAssistantMetrics(meta?: ChatResponseMeta) {
  if (!meta) {
    return [];
  }

  const metrics: Array<{ key: string; label: string; value: string }> = [];
  const outputTokens = readMetaNumber(meta, 'output_tokens');
  const totalTokens = readMetaNumber(meta, 'total_tokens');
  const elapsedSeconds = readMetaNumber(meta, 'elapsed_seconds');
  let tokensPerSecond = readMetaNumber(meta, 'tokens_per_second');
  const ttft = readMetaNumber(meta, 'time_to_first_token_seconds');

  if (typeof totalTokens === 'number' && totalTokens > 0) {
    metrics.push({
      key: 'tokens',
      label: 'Token',
      value: `${formatCompactNumber(totalTokens)} tok`,
    });
  } else if (typeof outputTokens === 'number' && outputTokens > 0) {
    metrics.push({
      key: 'tokens',
      label: 'Token',
      value: `${formatCompactNumber(outputTokens)} tok`,
    });
  }

  if (typeof elapsedSeconds === 'number' && elapsedSeconds > 0) {
    metrics.push({
      key: 'elapsed',
      label: 'Sure',
      value: formatDuration(elapsedSeconds),
    });
  }

  if (
    (typeof tokensPerSecond !== 'number' || tokensPerSecond <= 0)
    && typeof elapsedSeconds === 'number'
    && elapsedSeconds > 0
  ) {
    const rateBase = outputTokens ?? totalTokens;
    if (typeof rateBase === 'number' && rateBase > 0) {
      tokensPerSecond = rateBase / elapsedSeconds;
    }
  }

  if (typeof tokensPerSecond === 'number' && tokensPerSecond > 0) {
    const roundedRate =
      tokensPerSecond >= 100 ? Math.round(tokensPerSecond) : Number(tokensPerSecond.toFixed(1));
    metrics.push({
      key: 'speed',
      label: 'Hiz',
      value: `${formatCompactNumber(roundedRate)} tok/sn`,
    });
  }

  if (typeof ttft === 'number' && ttft > 0) {
    metrics.push({
      key: 'ttft',
      label: 'TTFT',
      value: formatDuration(ttft),
    });
  }

  return metrics;
}

function ContextUsageCard({
  meta,
  fallbackContextLength,
}: {
  meta?: ChatResponseMeta;
  fallbackContextLength?: number | null;
}) {
  const usage = resolveContextUsage(meta, fallbackContextLength);
  if (!usage) {
    return null;
  }

  return (
    <div
      className="mr-6 rounded-xl p-3"
      style={{
        background: 'rgba(255,255,255,0.035)',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5 text-[12px] leading-5">
            <div style={{ color: 'var(--color-text-secondary)' }}>
            Current conversation tokens: <span className="font-semibold text-white">{usage.inputTokens}</span>
            </div>
            <div style={{ color: 'var(--color-text-secondary)' }}>
            Total loaded context: <span className="font-semibold text-white">{usage.contextLength}</span>
            </div>
          <div style={{ color: 'var(--color-text-muted)' }}>
            {formatPercent(usage.usedPercent)} used ({formatPercent(usage.remainingPercent)} left)
          </div>
        </div>
        <div className="flex min-w-[60px] flex-col items-center gap-2">
          <div
            className="relative h-11 w-11 rounded-full"
            style={{
              background: `conic-gradient(#60a5fa ${usage.usedPercent}%, rgba(255,255,255,0.08) 0)`,
            }}
          >
            <div
              className="absolute inset-[4px] flex items-center justify-center rounded-full text-[10px] font-semibold"
              style={{ background: 'var(--color-bg-surface)', color: '#93c5fd' }}
            >
              {Math.round(usage.usedPercent)}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => <h1 className="mb-3 text-lg font-semibold text-white">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-3 text-base font-semibold text-white">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-2 text-sm font-semibold text-white">{children}</h3>,
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote
            className="mb-3 border-l-2 pl-3 italic"
            style={{ borderColor: 'rgba(99, 102, 241, 0.35)', color: 'var(--color-text-secondary)' }}
          >
            {children}
          </blockquote>
        ),
        pre: ({ children }) => (
          <pre
            className="mb-3 overflow-x-auto rounded-lg p-3 text-[12px]"
            style={{ background: 'rgba(0,0,0,0.18)' }}
          >
            {children}
          </pre>
        ),
        code: ({ children }) => (
          <code
            className="rounded px-1.5 py-0.5 text-[12px]"
            style={{ background: 'rgba(255,255,255,0.06)', color: '#c7d2fe' }}
          >
            {children}
          </code>
        ),
        table: ({ children }) => (
          <div className="mb-3 overflow-x-auto last:mb-0">
            <table
              className="min-w-full border-collapse text-left text-[12px]"
              style={{ border: '1px solid var(--color-border)' }}
            >
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => (
          <thead style={{ background: 'rgba(255,255,255,0.04)' }}>{children}</thead>
        ),
        th: ({ children }) => (
          <th
            className="px-3 py-2 font-semibold"
            style={{ borderBottom: '1px solid var(--color-border)' }}
          >
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td
            className="px-3 py-2 align-top"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
          >
            {children}
          </td>
        ),
        strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
        hr: () => <hr className="my-3" style={{ borderColor: 'var(--color-border)' }} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function ToolResultCard({ result }: { result: ToolResult }) {
  const [expanded, setExpanded] = useState(false);
  let parsed: string;
  try {
    parsed = JSON.stringify(JSON.parse(result.result), null, 2);
  } catch {
    parsed = result.result;
  }

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: 'rgba(245, 158, 11, 0.06)',
        border: '1px solid rgba(245, 158, 11, 0.15)',
      }}
    >
      <div
        className="mb-1 px-0.5 text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'rgba(245, 158, 11, 0.72)' }}
      >
        ikas MCP
      </div>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left"
        style={{ color: '#fbbf24' }}
      >
        <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <span className="font-mono font-semibold">{result.tool}</span>
        <span style={{ color: 'rgba(245, 158, 11, 0.5)' }}>
          ({Object.keys(result.arguments).length} arg)
        </span>
        <span className="ml-auto text-[10px]" style={{ color: 'rgba(245, 158, 11, 0.6)' }}>
          {expanded ? 'Gizle' : 'Goster'}
        </span>
      </button>
      {expanded && (
        <pre
          className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md p-2 text-[11px]"
          style={{
            background: 'rgba(0,0,0,0.2)',
            color: 'rgba(245, 158, 11, 0.7)',
          }}
        >
          {parsed}
        </pre>
      )}
    </div>
  );
}

function SuggestionSavedCard({ info }: { info: SuggestionSavedInfo }) {
  const fieldLabels: Record<string, string> = {
    suggested_name: 'Urun Adi',
    suggested_meta_title: 'Meta Title',
    suggested_meta_description: 'Meta Description',
    suggested_description: 'Aciklama (TR)',
    suggested_description_en: 'Aciklama (EN)',
  };

  const entries = Object.entries(info.fields).filter(([, v]) => v.trim());

  return (
    <div
      className="rounded-lg px-3 py-2.5 text-xs"
      style={{
        background: 'rgba(34, 197, 94, 0.08)',
        border: '1px solid rgba(34, 197, 94, 0.2)',
      }}
    >
      <div
        className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'rgba(34, 197, 94, 0.8)' }}
      >
        Oneri Kaydedildi
      </div>
      <div className="space-y-1">
        {entries.map(([key, value]) => (
          <div key={key} className="flex gap-2">
            <span
              className="flex-shrink-0 font-medium"
              style={{ color: 'rgba(34, 197, 94, 0.7)', minWidth: '90px' }}
            >
              {fieldLabels[key] || key}:
            </span>
            <span style={{ color: 'rgba(34, 197, 94, 0.9)' }}>
              {value.length > 80 ? value.slice(0, 80) + '...' : value}
            </span>
          </div>
        ))}
      </div>
      <div
        className="mt-2 text-[11px]"
        style={{ color: 'rgba(34, 197, 94, 0.5)' }}
      >
        Oneriler sekmesinden onaylayip ikas'a uygulayabilirsiniz.
      </div>
    </div>
  );
}

function ThinkingBlock({
  text,
  assistantLabel,
  durationSeconds,
}: {
  text: string;
  assistantLabel: string;
  durationSeconds?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const title =
    typeof durationSeconds === 'number' && durationSeconds > 0
      ? `Thought for ${formatThoughtDuration(durationSeconds)}`
      : `${assistantLabel} dusunce`;
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: 'rgba(139, 92, 246, 0.06)',
        border: '1px solid rgba(139, 92, 246, 0.15)',
      }}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left"
        style={{ color: '#a78bfa' }}
      >
        <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <span className="font-medium">{title}</span>
        <span className="ml-auto text-[10px]" style={{ color: 'rgba(139, 92, 246, 0.6)' }}>
          {expanded ? 'Gizle' : 'Goster'}
        </span>
      </button>
      {expanded && (
        <div
          className="mt-2 text-[12px] leading-relaxed"
          style={{ color: 'rgba(139, 92, 246, 0.78)' }}
        >
          <MarkdownMessage content={text} />
        </div>
      )}
    </div>
  );
}

function getRoleMeta(role: ChatMessage['role'], assistantLabel: string) {
  if (role === 'user') {
    return {
      label: 'Sen',
      color: '#c7d2fe',
    };
  }

  if (role === 'assistant') {
    return {
      label: assistantLabel,
      color: 'var(--color-text-muted)',
    };
  }

  return {
    label: 'Akis',
    color: 'var(--color-text-muted)',
  };
}

function MessageBubble({
  msg,
  assistantLabel,
  fallbackContextLength,
}: {
  msg: ChatMessage;
  assistantLabel: string;
  fallbackContextLength?: number | null;
}) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const isAssistant = msg.role === 'assistant';
  const roleMeta = getRoleMeta(msg.role, assistantLabel);
  const assistantMetrics = isAssistant ? getAssistantMetrics(msg.meta) : [];
  const thoughtDuration = readMetaNumber(msg.meta, 'elapsed_seconds');

  return (
    <div className="space-y-2">
      {isAssistant && msg.toolResults && msg.toolResults.length > 0 && (
        <div className="mr-6 space-y-1.5">
          {msg.toolResults.map((tr, i) => (
            <ToolResultCard key={i} result={tr} />
          ))}
        </div>
      )}

      {isAssistant && msg.suggestionSaved ? (
        <div className="mr-6">
          <SuggestionSavedCard info={msg.suggestionSaved} />
        </div>
      ) : null}

      {isAssistant && msg.thinking ? (
        <ThinkingBlock
          text={msg.thinking}
          assistantLabel={assistantLabel}
          durationSeconds={thoughtDuration}
        />
      ) : null}

      <div className={`${isUser ? 'ml-6' : isSystem ? '' : 'mr-6'}`}>
        <div
          className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-[0.16em]"
          style={{ color: roleMeta.color }}
        >
          {roleMeta.label}
        </div>
        <div
          className="rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed"
          style={{
            background: isUser
              ? 'rgba(99, 102, 241, 0.15)'
              : isSystem
                ? 'rgba(255, 255, 255, 0.03)'
                : 'var(--color-bg-elevated)',
            border: isSystem ? 'none' : `1px solid ${isUser ? 'rgba(99, 102, 241, 0.2)' : 'var(--color-border)'}`,
            color: isUser
              ? '#c7d2fe'
              : isSystem
                ? 'var(--color-text-muted)'
                : 'var(--color-text-primary)',
            fontStyle: isSystem ? 'italic' : 'normal',
            fontSize: isSystem ? '12px' : '13px',
          }}
        >
          {isAssistant ? <MarkdownMessage content={msg.content} /> : msg.content}
        </div>
      </div>

      {isAssistant && assistantMetrics.length > 0 ? (
        <div className="mr-6 flex flex-wrap justify-end gap-1.5">
          {assistantMetrics.map((metric) => (
            <div
              key={metric.key}
              className="rounded-full px-2.5 py-1 text-[10px] font-medium"
              style={{
                background: 'rgba(255,255,255,0.04)',
                color: 'var(--color-text-muted)',
                border: '1px solid rgba(255,255,255,0.08)',
              }}
            >
              {metric.label}: {metric.value}
            </div>
          ))}
        </div>
      ) : null}

      {isAssistant ? <ContextUsageCard meta={msg.meta} fallbackContextLength={fallbackContextLength} /> : null}
    </div>
  );
}

function StatusPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'neutral' | 'success' | 'warn';
}) {
  const palette = {
    neutral: {
      background: 'rgba(148, 163, 184, 0.08)',
      color: 'var(--color-text-secondary)',
      border: '1px solid rgba(148, 163, 184, 0.12)',
    },
    success: {
      background: 'rgba(16, 185, 129, 0.10)',
      color: '#34d399',
      border: '1px solid rgba(16, 185, 129, 0.16)',
    },
    warn: {
      background: 'rgba(245, 158, 11, 0.10)',
      color: '#fbbf24',
      border: '1px solid rgba(245, 158, 11, 0.16)',
    },
  } as const;

  const style = palette[tone];

  return (
    <div
      className="rounded-full px-2 py-1 text-[10px] font-medium"
      style={style}
      title={`${label}: ${value}`}
    >
      {label}: {value}
    </div>
  );
}

export default function ChatPanel({
  productId,
  productName,
  productCategory,
  seoScore,
  product,
  score,
}: Props) {
  const settingsQ = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 5 * 60 * 1000,
  });
  const configuredModel = settingsQ.data?.ai_model_name?.trim();
  const configuredProvider = settingsQ.data?.ai_provider?.trim();
  const lmStatusQ = useQuery({
    queryKey: ['lm-studio-live-status'],
    queryFn: () => getLmStudioLiveStatus(),
    enabled: configuredProvider === 'lm-studio',
    staleTime: 2_000,
    refetchInterval: configuredProvider === 'lm-studio' ? 5_000 : false,
  });
  const configuredAssistantLabel = configuredModel || configuredProvider || 'AI modeli';
  const displayProductName = productName || product?.name;
  const displayProductCategory = productCategory ?? product?.category ?? null;
  const displaySeoScore = seoScore ?? score?.total_score ?? null;
  const {
    messages,
    isLoading,
    pendingSince,
    mcpState,
    sendMessage,
    cancelMessage,
    clearHistory,
    connect,
    disconnect,
  } = useChat({
    id: productId,
    name: displayProductName,
    category: displayProductCategory,
    score: displaySeoScore,
    assistantLabel: configuredAssistantLabel,
  });
  const [input, setInput] = useState('');
  const [liveElapsedSeconds, setLiveElapsedSeconds] = useState(0);
  const [paramTrigger, setParamTrigger] = useState<ParamTriggerState | null>(null);
  const [activeParamIndex, setActiveParamIndex] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const promptParamOptions = buildPromptParamOptions(product, score);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [messages]);

  useEffect(() => {
    if (pendingSince === null) {
      setLiveElapsedSeconds(0);
      return;
    }

    const updateElapsed = () => {
      setLiveElapsedSeconds((performance.now() - pendingSince) / 1000);
    };

    updateElapsed();
    const intervalId = window.setInterval(updateElapsed, 100);
    return () => window.clearInterval(intervalId);
  }, [pendingSince]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }

    textarea.style.height = '0px';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
  }, [input]);

  useEffect(() => {
    setInput('');
    setParamTrigger(null);
    setActiveParamIndex(0);
  }, [productId]);

  const latestAssistant = [...messages].reverse().find(
    (msg) => msg.role === 'assistant' && typeof msg.meta?.model === 'string',
  );
  const liveContextLength = lmStatusQ.data?.selected_model?.context_length ?? null;
  let sessionTotalTokens = 0;
  for (const msg of messages) {
    if (msg.role !== 'assistant') {
      continue;
    }

    const totalTokens = readMetaNumber(msg.meta, 'total_tokens');
    const inputTokens = readMetaNumber(msg.meta, 'input_tokens');
    const outputTokens = readMetaNumber(msg.meta, 'output_tokens');
    sessionTotalTokens += totalTokens ?? ((inputTokens ?? 0) + (outputTokens ?? 0));
  }
  const assistantLabel =
    typeof latestAssistant?.meta?.model === 'string'
      ? String(latestAssistant.meta.model)
      : configuredAssistantLabel;

  const starterPrompts: StarterPrompt[] = [
    {
      label: 'SEO metriklerini yorumla',
      template:
        '@local Bu mevcut SEO metriklerini alan bazinda yorumla ve sadece bu skorlara gore 3 oncelikli tavsiye ver.\n\n{seoMetricsSummary}',
    },
    {
      label: 'Urun aciklamasini yorumla',
      template:
        '@local Bu urunun mevcut aciklamasini yorumla. Yalnizca eldeki metni kullan.\n\n{productDescription}',
    },
    {
      label: 'Meta titlei yorumla',
      template:
        '@local Bu mevcut meta titlei SEO acisindan yorumla.\n\n{productMetaTitle}',
    },
    {
      label: 'Meta descriptioni yorumla',
      template:
        '@local Bu mevcut meta descriptioni SEO acisindan yorumla.\n\n{productMetaDescription}',
    },
  ];

  const showStarterState = messages.length === 0 || messages.every((msg) => msg.role === 'system');
  const filteredParamOptions = paramTrigger
    ? promptParamOptions.filter((option) => (
      !paramTrigger.query
      || option.searchText.includes(paramTrigger.query.toLowerCase())
      || option.key.toLowerCase().includes(paramTrigger.query.toLowerCase())
    ))
    : [];
  const showParamMenu = filteredParamOptions.length > 0;

  const syncParamTrigger = (value: string, caretPosition: number | null) => {
    setParamTrigger(getParamTriggerState(value, caretPosition));
    setActiveParamIndex(0);
  };

  const applyParamOption = (option: PromptParamOption) => {
    if (!paramTrigger) {
      return;
    }

    const closingIndex = input.indexOf('}', paramTrigger.start);
    const replaceEnd =
      closingIndex !== -1 && closingIndex >= paramTrigger.end
        ? closingIndex + 1
        : paramTrigger.end;
    const nextValue = `${input.slice(0, paramTrigger.start)}${option.value}${input.slice(replaceEnd)}`;
    const nextCaretPosition = paramTrigger.start + option.value.length;

    setInput(nextValue);
    setParamTrigger(null);
    setActiveParamIndex(0);

    window.requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (!textarea) {
        return;
      }
      textarea.focus();
      textarea.setSelectionRange(nextCaretPosition, nextCaretPosition);
    });
  };

  const submitPrompt = (text: string) => {
    const value = resolvePromptTemplate(text, promptParamOptions).trim();
    if (!value) return;
    sendMessage(value);
    setInput('');
    setParamTrigger(null);
    setActiveParamIndex(0);
  };

  const handleSend = () => submitPrompt(input);
  const handleStarterPrompt = (prompt: StarterPrompt) => submitPrompt(prompt.template);

  return (
    <div
      className="flex h-full flex-col overflow-hidden rounded-xl"
      style={{
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div
        className="px-4 py-3"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <div
                className="flex h-6 w-6 items-center justify-center rounded-md"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
              >
                <svg className="h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <span className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                AI Chat
              </span>
            </div>

            {displayProductName && (
              <div className="mt-2 min-w-0">
                <div className="truncate text-[18px] font-semibold text-white">
                  {displayProductName}
                </div>
                <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                  {displayProductCategory || 'Kategori yok'}
                  {typeof displaySeoScore === 'number' ? ` | SEO ${displaySeoScore}/100` : ''}
                </div>
              </div>
            )}
          </div>

          {messages.length > 0 && (
            <button
              onClick={clearHistory}
              className="text-[11px] font-medium transition-all"
              style={{ color: 'var(--color-text-muted)' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-secondary)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-muted)')}
            >
              Temizle
            </button>
          )}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <StatusPill label="Model" value={assistantLabel} tone="neutral" />
          <StatusPill
            label="MCP"
            value={mcpState.initialized ? 'bagli' : mcpState.hasToken ? 'bekliyor' : 'kapali'}
            tone={mcpState.initialized ? 'success' : mcpState.hasToken ? 'warn' : 'neutral'}
          />
          {mcpState.initialized && (
            <StatusPill
              label="Arac"
              value={String(mcpState.toolCount)}
              tone="success"
            />
          )}
          {sessionTotalTokens > 0 && (
            <StatusPill
              label="Token"
              value={`${formatCompactNumber(sessionTotalTokens)} tok`}
              tone="neutral"
            />
          )}
          {typeof liveContextLength === 'number' && liveContextLength > 0 && (
            <StatusPill
              label="Context"
              value={formatCompactNumber(liveContextLength)}
              tone="neutral"
            />
          )}
          {isLoading && (
            <StatusPill
              label="Sure"
              value={formatDuration(liveElapsedSeconds)}
              tone="warn"
            />
          )}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
        {showStarterState && (
          <div
            className="rounded-2xl p-4 text-center"
            style={{
              background: 'linear-gradient(180deg, rgba(99, 102, 241, 0.10), rgba(17, 24, 39, 0.02))',
              border: '1px solid rgba(99, 102, 241, 0.15)',
            }}
          >
            <div
              className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl"
              style={{ background: 'rgba(99, 102, 241, 0.12)', color: '#c7d2fe' }}
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="mt-3 text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              Secili urunun mevcut SEO metrikleri ve eldeki alanlariyla sohbet hazir.
            </p>
            <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              `@local` ile mevcut baglami yorumlat. {'{'} yazarak `productDescription` veya `seoMetricsSummary`
              gibi alanlari mesaja ekleyebilirsin.
            </p>

            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {starterPrompts.map((prompt) => (
                <button
                  key={prompt.label}
                  onClick={() => handleStarterPrompt(prompt)}
                  disabled={isLoading}
                  className="rounded-full px-3 py-1.5 text-[11px] font-medium transition-all hover:opacity-90 disabled:opacity-40"
                  style={{
                    background: 'rgba(99, 102, 241, 0.12)',
                    color: '#c7d2fe',
                    border: '1px solid rgba(99, 102, 241, 0.2)',
                  }}
                >
                  {prompt.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            msg={msg}
            assistantLabel={assistantLabel}
            fallbackContextLength={liveContextLength}
          />
        ))}

        {isLoading && (
          <div
            className="mr-6 rounded-xl px-4 py-3"
            style={{
              background: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="typing-dot h-1.5 w-1.5 rounded-full" style={{ background: 'var(--color-primary-light)' }} />
                  <span className="typing-dot h-1.5 w-1.5 rounded-full" style={{ background: 'var(--color-primary-light)' }} />
                  <span className="typing-dot h-1.5 w-1.5 rounded-full" style={{ background: 'var(--color-primary-light)' }} />
                </div>
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {assistantLabel} dusunuyor...
                </span>
              </div>
            </div>
            <div
              className="mt-2 text-[11px]"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Sure: {formatDuration(liveElapsedSeconds)}
            </div>
          </div>
        )}
      </div>

      <div className="p-3" style={{ borderTop: '1px solid var(--color-border)' }}>
        <div className="flex items-end gap-2">
          <div className="relative flex-1">
            {showParamMenu && (
              <div
                className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl"
                style={{
                  background: 'rgba(15, 23, 42, 0.98)',
                  border: '1px solid rgba(99, 102, 241, 0.22)',
                  boxShadow: '0 14px 40px rgba(0, 0, 0, 0.34)',
                }}
              >
                <div
                  className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em]"
                  style={{
                    color: 'var(--color-text-muted)',
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  Parametreler
                </div>
                <div className="max-h-64 overflow-y-auto p-1.5">
                  {filteredParamOptions.slice(0, 8).map((option, index) => (
                    <button
                      key={option.key}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        applyParamOption(option);
                      }}
                      className="mb-1 block w-full rounded-lg px-2.5 py-2 text-left last:mb-0"
                      style={{
                        background:
                          index === activeParamIndex
                            ? 'rgba(99, 102, 241, 0.14)'
                            : 'rgba(255,255,255,0.02)',
                        border:
                          index === activeParamIndex
                            ? '1px solid rgba(99, 102, 241, 0.28)'
                            : '1px solid transparent',
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px]" style={{ color: '#c7d2fe' }}>
                          {`{${option.key}}`}
                        </span>
                        <span className="text-[11px] font-medium text-white">{option.label}</span>
                      </div>
                      <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                        {option.description}
                      </div>
                      <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                        {option.preview}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <textarea
              ref={textareaRef}
              value={input}
              rows={1}
              onChange={(e) => {
                const nextValue = e.target.value;
                setInput(nextValue);
                syncParamTrigger(nextValue, e.target.selectionStart);
              }}
              onSelect={(e) => {
                syncParamTrigger(e.currentTarget.value, e.currentTarget.selectionStart);
              }}
              onKeyDown={(e) => {
                if (showParamMenu) {
                  if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    setActiveParamIndex((prev) => (prev + 1) % filteredParamOptions.slice(0, 8).length);
                    return;
                  }

                  if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    setActiveParamIndex((prev) => (
                      prev === 0 ? filteredParamOptions.slice(0, 8).length - 1 : prev - 1
                    ));
                    return;
                  }

                  if ((e.key === 'Enter' || e.key === 'Tab') && filteredParamOptions[activeParamIndex]) {
                    e.preventDefault();
                    applyParamOption(filteredParamOptions[activeParamIndex]);
                    return;
                  }

                  if (e.key === 'Escape') {
                    e.preventDefault();
                    setParamTrigger(null);
                    return;
                  }
                }

                if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder={
                displayProductName
                  ? `${displayProductName} icin soru sorun. { ile hazir alan ekleyin...`
                  : 'Mesaj yazin... { ile parametre ekleyin.'
              }
              className="min-h-[44px] w-full resize-none rounded-lg px-3 py-2 text-[13px] outline-none transition-all"
              style={{
                background: 'var(--color-bg-base)',
                border: '1px solid var(--color-border-light)',
                color: 'var(--color-text-primary)',
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-border-light)';
                setParamTrigger(null);
              }}
            />
            <div className="mt-1 px-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {'{'} ile `productDescription`, `productMetaTitle` veya `seoMetricsSummary` gibi alanlari hizlica ekle.
            </div>
          </div>
          <button
            onClick={isLoading ? cancelMessage : handleSend}
            disabled={!isLoading && !input.trim()}
            className={`flex min-h-[44px] flex-shrink-0 items-center justify-center rounded-lg px-3 text-white transition-all hover:opacity-90 disabled:opacity-30 ${isLoading ? 'min-w-[64px]' : 'w-11'}`}
            style={{
              background: isLoading
                ? 'linear-gradient(135deg, #ef4444, #f97316)'
                : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            }}
            title={isLoading ? 'Aktif istegi durdur' : 'Mesaji gonder'}
          >
            {isLoading ? (
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em]">Stop</span>
            ) : (
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

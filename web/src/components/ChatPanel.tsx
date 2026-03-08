import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getLmStudioLiveStatus, getSettings } from '../api/client';
import { useChat, type ChatMessage, type MCPState } from '../hooks/useChat';
import type { ChatResponseMeta, ToolResult } from '../types';

interface Props {
  productId?: string;
  productName?: string;
  productCategory?: string | null;
  seoScore?: number | null;
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
        <p className="mt-2 whitespace-pre-wrap text-[12px] leading-relaxed" style={{ color: 'rgba(139, 92, 246, 0.7)' }}>
          {text}
        </p>
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

function MentionGuide({ mcpState }: { mcpState: MCPState }) {
  const examples = [
    '@local Bu urunun SEO skorunu yorumla',
    '@ikas Bu urunun canli stok ve fiyatini getir',
    '@ikas @local Varyantlari cek ve kisaca ozetle',
  ];
  const queryCapabilities = [
    {
      title: 'Customer Management',
      items: ['listCustomer', 'listCustomerAttribute'],
    },
    {
      title: 'Location Management',
      items: ['listCountry', 'listState', 'listCity', 'listDistrict', 'listTown'],
    },
    {
      title: 'Merchant',
      items: ['getMerchant', 'getMerchantLicence'],
    },
    {
      title: 'Sales & Payments',
      items: ['listAbandonedCheckouts'],
    },
    {
      title: 'Product Management',
      items: ['listProduct', 'listProductAttribute', 'listProductBrand'],
    },
    {
      title: 'Order Management',
      items: ['listOrder', 'listOrderTag', 'listOrderTransactions'],
    },
    {
      title: 'Settings',
      items: ['getGlobalTaxSettings', 'listShippingSettings', 'listTaxSettings'],
    },
  ];
  const mutationCapabilities = [
    {
      title: 'Customer Management',
      items: ['updateCustomer', 'addCustomerTimelineEntry'],
    },
    {
      title: 'App Integration',
      items: ['createMerchantAppPayment', 'saveWebhooks', 'deleteWebhook', 'getAppDemoDay'],
    },
    {
      title: 'Sales Channel',
      items: ['updateSalesChannel'],
    },
    {
      title: 'Order Management',
      items: ['createOrderWithTransactions', 'fulfillOrder', 'cancelFulfillment', 'cancelOrderLine', 'refundOrderLine', 'updateOrderPackageStatus', 'addOrderInvoice', 'removeOrderInvoice', 'downloadOrderInvoice', 'approvePendingOrderTransactions'],
    },
    {
      title: 'Product Management',
      items: ['createProduct', 'updateProduct', 'deleteProductList', 'addVariantToProduct', 'removeVariantFromProduct', 'saveVariantStocks', 'updateVariantPrices'],
    },
    {
      title: 'Campaign Management',
      items: ['createCampaign', 'updateCampaign', 'deleteCampaignList', 'addCouponsToCampaign'],
    },
    {
      title: 'Storefront Management',
      items: ['createStorefrontJSScript', 'updateStorefrontJSScript', 'deleteStorefrontJSScript'],
    },
    {
      title: 'Timeline Management',
      items: ['addCustomTimelineEntry', 'addOrderTimelineEntry'],
    },
  ];

  return (
    <details
      className="rounded-xl px-3 py-2.5"
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid var(--color-border)',
      }}
    >
      <summary
        className="cursor-pointer text-[12px] font-medium"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        Mentionlar ve MCP
      </summary>
      <div className="mt-3 space-y-3 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
        <p>
          Canli ikas verisini sadece <strong>@ikas</strong> ile aciyoruz. Mention yoksa sohbet
          varsayilan olarak local baglamda kalir ve MCP cagrisi yapmaz.
        </p>
        <p>
          Teknik olarak ikas MCP arka planda generic bir GraphQL katmani sunuyor; uygulama bunu
          sana operasyon listesi olarak gosterip chat tarafinda kullanilabilir hale getiriyor.
        </p>
        <p>
          Model, sadece arac cagirmakla kalmaz; onerilerini de desteklenen ikas operasyon adlariyla
          somut bir sonraki adima donusturmeye calisir.
        </p>
        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
            Yonetim
          </div>
          <ul className="space-y-1">
            <li>- <strong>@local</strong>: sadece mevcut baglamla cevap ver, arac kullanma</li>
            <li>- <strong>@ikas</strong>: mumkunse canli ikas MCP araci kullan</li>
            <li>- <strong>@ikas @local</strong>: veriyi MCP ile cek, yaniti model ozetlesin</li>
          </ul>
        </div>
        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
            Ornekler
          </div>
          <ul className="space-y-1">
            {examples.map((example) => (
              <li key={example}>- {example}</li>
            ))}
          </ul>
        </div>

        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
            Query yetenekleri
          </div>
          <div className="space-y-2">
            {queryCapabilities.map((group) => (
              <div
                key={group.title}
                className="rounded-lg px-2.5 py-2"
                style={{ background: 'rgba(255,255,255,0.03)' }}
              >
                <div className="text-[11px] font-semibold text-white">{group.title}</div>
                <div className="mt-1 text-[11px] leading-relaxed">
                  {group.items.join(', ')}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
            Mutation yetenekleri
          </div>
          <div className="space-y-2">
            {mutationCapabilities.map((group) => (
              <div
                key={group.title}
                className="rounded-lg px-2.5 py-2"
                style={{ background: 'rgba(255,255,255,0.03)' }}
              >
                <div className="text-[11px] font-semibold text-white">{group.title}</div>
                <div className="mt-1 text-[11px] leading-relaxed">
                  {group.items.join(', ')}
                </div>
              </div>
            ))}
          </div>
        </div>

        {mcpState.initialized && mcpState.tools.length > 0 ? (
          <div>
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em]">
              Kullanilabilir operasyonlar ({mcpState.toolCount})
            </div>
            <div className="space-y-2">
              {mcpState.tools.slice(0, 10).map((tool) => (
                <div
                  key={tool.name}
                  className="rounded-lg px-2.5 py-2"
                  style={{ background: 'rgba(245, 158, 11, 0.05)' }}
                >
                  <div className="font-mono text-[11px]" style={{ color: '#fbbf24' }}>
                    {tool.name}
                  </div>
                  <div className="mt-1 text-[11px] leading-relaxed">
                    {tool.description || 'Aciklama gelmedi.'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p>
            {mcpState.hasToken
              ? 'Token var ama arac listesi gelmedi. Bu durumda @ikas yazsan da model kullanabilecek arac goremeyebilir.'
              : 'MCP token olmadigi icin @ikas mentioni canli veri cektiremez.'}
          </p>
        )}
      </div>
    </details>
  );
}

export default function ChatPanel({
  productId,
  productName,
  productCategory,
  seoScore,
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
    name: productName,
    category: productCategory,
    score: seoScore,
    assistantLabel: configuredAssistantLabel,
  });
  const [input, setInput] = useState('');
  const [liveElapsedSeconds, setLiveElapsedSeconds] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

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

  const starterPrompts = [
    '@local Bu urunun SEO skorunu hizlica acikla',
    '@local Bu urun icin 3 yeni baslik oner',
    mcpState.initialized
      ? '@ikas Bu urunun canli stok ve fiyat durumunu kontrol et'
      : '@local Bu urun icin aciklama iyilestirme plani cikar',
  ];

  const showStarterState = messages.every((msg) => msg.role === 'system');

  const submitPrompt = (text: string) => {
    const value = text.trim();
    if (!value) return;
    sendMessage(value);
    setInput('');
  };

  const handleSend = () => submitPrompt(input);

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

            {productName && (
              <div className="mt-2 min-w-0">
                <div className="truncate text-[18px] font-semibold text-white">
                  {productName}
                </div>
                <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                  {productCategory || 'Kategori yok'}
                  {typeof seoScore === 'number' ? ` | SEO ${seoScore}/100` : ''}
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

        <div className="mt-3">
          <MentionGuide mcpState={mcpState} />
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
              Secili urun icin uc tarafli sohbet hazir.
            </p>
            <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              `@local` ile mevcut baglami yorumlat, `@ikas` ile canli veri iste.
            </p>

            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {starterPrompts.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => submitPrompt(prompt)}
                  disabled={isLoading}
                  className="rounded-full px-3 py-1.5 text-[11px] font-medium transition-all hover:opacity-90 disabled:opacity-40"
                  style={{
                    background: 'rgba(99, 102, 241, 0.12)',
                    color: '#c7d2fe',
                    border: '1px solid rgba(99, 102, 241, 0.2)',
                  }}
                >
                  {prompt}
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
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
                handleSend();
              }
            }}
            placeholder={
              productName
                ? `${productName} icin soru sorun. @local veya @ikas ile yonlendirebilirsiniz...`
                : 'Mesaj yazin...'
            }
            className="flex-1 rounded-lg px-3 py-2 text-[13px] outline-none transition-all"
            style={{
              background: 'var(--color-bg-base)',
              border: '1px solid var(--color-border-light)',
              color: 'var(--color-text-primary)',
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--color-border-light)')}
          />
          <button
            onClick={isLoading ? cancelMessage : handleSend}
            disabled={!isLoading && !input.trim()}
            className={`flex h-9 flex-shrink-0 items-center justify-center rounded-lg px-3 text-white transition-all hover:opacity-90 disabled:opacity-30 ${isLoading ? 'min-w-[64px]' : 'w-9'}`}
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

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../../hooks/useChat';
import type { ChatResponseMeta, SuggestionSavedInfo, ToolResult } from '../../types';
import { formatPercent, formatThoughtDuration, getAssistantMetrics, formatCompactNumber, readMetaNumber, resolveContextUsage } from './chatUtils';
import { extractSuggestionOptions, getSuggestionCardPalette, type SuggestionOption } from './suggestionUtils';

// ── MarkdownMessage ───────────────────────────────────────────────────────────

export function MarkdownMessage({ content }: { content: string }) {
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
          <th className="px-3 py-2 font-semibold" style={{ borderBottom: '1px solid var(--color-border)' }}>
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 align-top" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
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

// ── SuggestionCards ───────────────────────────────────────────────────────────

function SuggestionCards({
  options,
  onApplyOption,
  disabled,
}: {
  options: SuggestionOption[];
  onApplyOption: (option: SuggestionOption, index: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="mt-4 flex flex-wrap gap-3">
      {options.map((option, index) => {
        const palette = getSuggestionCardPalette(option.tone, index);

        return (
          <div
            key={`${option.tone}-${index}`}
            className="relative flex min-w-[220px] flex-1 flex-col overflow-hidden rounded-2xl p-4 transition-all duration-200 hover:-translate-y-0.5"
            style={{
              background: palette.background,
              border: `1px solid ${palette.border}`,
              boxShadow: palette.shadow,
            }}
          >
            <div
              className="absolute inset-x-0 top-0 h-1"
              style={{ background: `linear-gradient(90deg, ${palette.accent}, transparent)` }}
            />
            <div className="flex items-center justify-between gap-3">
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]"
                style={{ background: palette.badgeBackground, color: palette.badgeColor }}
              >
                {option.tone}
              </span>
              <span className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                Secenek {index + 1}
              </span>
            </div>

            <p className="mt-3 flex-1 text-sm leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>
              {option.value}
            </p>

            <button
              type="button"
              onClick={() => onApplyOption(option, index)}
              disabled={disabled}
              className="mt-4 rounded-xl px-3 py-2 text-xs font-semibold transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50"
              style={{
                background: palette.buttonBackground,
                border: `1px solid ${palette.buttonBorder}`,
                color: palette.buttonColor,
              }}
            >
              Bunu Uygula
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ── AssistantMessageContent ───────────────────────────────────────────────────

function AssistantMessageContent({
  content,
  onApplyOption,
  applyDisabled,
}: {
  content: string;
  onApplyOption?: (option: SuggestionOption, index: number) => void;
  applyDisabled?: boolean;
}) {
  const { markdownContent, options } = extractSuggestionOptions(content);

  return (
    <div className="space-y-4">
      {markdownContent ? <MarkdownMessage content={markdownContent} /> : null}
      {options.length > 0 && onApplyOption ? (
        <SuggestionCards options={options} onApplyOption={onApplyOption} disabled={applyDisabled} />
      ) : null}
    </div>
  );
}

// ── ToolResultCard ────────────────────────────────────────────────────────────

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
      style={{ background: 'rgba(245, 158, 11, 0.06)', border: '1px solid rgba(245, 158, 11, 0.15)' }}
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
          style={{ background: 'rgba(0,0,0,0.2)', color: 'rgba(245, 158, 11, 0.7)' }}
        >
          {parsed}
        </pre>
      )}
    </div>
  );
}

// ── SuggestionSavedCard ───────────────────────────────────────────────────────

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
      style={{ background: 'rgba(34, 197, 94, 0.08)', border: '1px solid rgba(34, 197, 94, 0.2)' }}
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
      <div className="mt-2 text-[11px]" style={{ color: 'rgba(34, 197, 94, 0.5)' }}>
        Oneriler sekmesinden onaylayip ikas'a uygulayabilirsiniz.
      </div>
    </div>
  );
}

// ── ThinkingBlock ─────────────────────────────────────────────────────────────

function ThinkingBlock({
  text,
  assistantLabel,
  durationSeconds,
}: {
  text: string;
  assistantLabel: string;
  durationSeconds?: number;
}) {
  const isLive = typeof durationSeconds !== 'number' || durationSeconds <= 0;
  const [expanded, setExpanded] = useState(isLive);

  useEffect(() => {
    if (isLive && text) {
      setExpanded(true);
    }
  }, [isLive, text]);

  const title =
    typeof durationSeconds === 'number' && durationSeconds > 0
      ? `Thought for ${formatThoughtDuration(durationSeconds)}`
      : `${assistantLabel} dusunce`;

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{ background: 'rgba(139, 92, 246, 0.06)', border: '1px solid rgba(139, 92, 246, 0.15)' }}
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
        <div className="mt-2 text-[12px] leading-relaxed" style={{ color: 'rgba(139, 92, 246, 0.78)' }}>
          <MarkdownMessage content={text} />
        </div>
      )}
    </div>
  );
}

// ── ContextUsageCard ──────────────────────────────────────────────────────────

export function ContextUsageCard({
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
      style={{ background: 'rgba(255,255,255,0.035)', border: '1px solid rgba(255,255,255,0.08)' }}
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

// ── MessageBubble ─────────────────────────────────────────────────────────────

function getRoleMeta(role: ChatMessage['role'], assistantLabel: string) {
  if (role === 'user') return { label: 'Sen', color: '#c7d2fe' };
  if (role === 'assistant') return { label: assistantLabel, color: 'var(--color-text-muted)' };
  return { label: 'Akis', color: 'var(--color-text-muted)' };
}

export function MessageBubble({
  msg,
  assistantLabel,
  fallbackContextLength,
  onApplyOption,
  applyDisabled,
}: {
  msg: ChatMessage;
  assistantLabel: string;
  fallbackContextLength?: number | null;
  onApplyOption?: (option: SuggestionOption, index: number) => void;
  applyDisabled?: boolean;
}) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const isAssistant = msg.role === 'assistant';
  const hasVisibleAssistantContent = isAssistant ? Boolean(msg.content.trim()) : true;
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

      {hasVisibleAssistantContent && (
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
              border: isSystem
                ? 'none'
                : `1px solid ${isUser ? 'rgba(99, 102, 241, 0.2)' : 'var(--color-border)'}`,
              color: isUser
                ? '#c7d2fe'
                : isSystem
                  ? 'var(--color-text-muted)'
                  : 'var(--color-text-primary)',
              fontStyle: isSystem ? 'italic' : 'normal',
              fontSize: isSystem ? '12px' : '13px',
            }}
          >
            {isAssistant ? (
              <AssistantMessageContent
                content={msg.content}
                onApplyOption={onApplyOption}
                applyDisabled={applyDisabled}
              />
            ) : msg.content}
          </div>
        </div>
      )}

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

      {isAssistant ? (
        <ContextUsageCard meta={msg.meta} fallbackContextLength={fallbackContextLength} />
      ) : null}
    </div>
  );
}

// Re-export SuggestionOption so ChatPanel can import from a single place
export type { SuggestionOption };
// Re-export formatCompactNumber used in ChatPanel header
export { formatCompactNumber };

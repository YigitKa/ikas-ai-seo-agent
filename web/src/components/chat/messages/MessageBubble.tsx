import { memo } from 'react';
import type { ChatMessage } from '../../../hooks/useChat';
import type { SuggestionOption } from '../suggestionUtils';
import { getAssistantMetrics, readMetaNumber } from '../chatUtils';
import ToolResultCard from './ToolResultCard';
import SuggestionSavedCard from './SuggestionSavedCard';
import ThinkingBlock from './ThinkingBlock';
import AssistantMessageContent from './AssistantContent';
import ContextUsageCard from './ContextUsageCard';
import CostCard from './CostCard';

const FAILED_RESPONSE_MARKER = 'Model nihai cevap uretmedi';

export function getRoleMeta(role: ChatMessage['role'], assistantLabel: string) {
  if (role === 'user') return { label: 'Sen', color: 'var(--color-text-brand-soft)' };
  if (role === 'assistant') return { label: assistantLabel, color: 'var(--color-text-muted)' };
  return { label: 'Akis', color: 'var(--color-text-muted)' };
}

function MessageBubble({
  msg,
  assistantLabel,
  fallbackContextLength,
  onApplyOption,
  onRetry,
  applyDisabled,
}: {
  msg: ChatMessage;
  assistantLabel: string;
  fallbackContextLength?: number | null;
  onApplyOption?: (option: SuggestionOption, index: number) => void;
  onRetry?: () => void;
  applyDisabled?: boolean;
}) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const isAssistant = msg.role === 'assistant';
  const isFailedResponse = isAssistant && msg.content.includes(FAILED_RESPONSE_MARKER);
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
            className="rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed shadow-sm"
            style={{
              background: isUser
                ? 'var(--chat-bubble-user-bg)'
                : isSystem
                  ? 'var(--chat-muted-card-bg)'
                  : 'var(--chat-bubble-assistant-bg)',
              border: isSystem
                ? 'none'
                : `1px solid ${isUser ? 'var(--chat-bubble-user-border)' : 'var(--chat-bubble-assistant-border)'}`,
              color: isUser
                ? 'var(--color-text-brand-soft)'
                : isSystem
                  ? 'var(--color-text-muted)'
                  : 'var(--color-text-primary)',
              fontStyle: isSystem ? 'italic' : 'normal',
              fontSize: isSystem ? '12px' : '13px',
              boxShadow: isSystem ? 'none' : 'var(--chat-bubble-shadow)',
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

      {isFailedResponse && onRetry && !applyDisabled ? (
        <div className="mr-6 mt-1">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors"
            style={{
              background: 'var(--tint-warning-soft)',
              border: '1px solid var(--color-border-warning)',
              color: 'var(--color-text-warning-soft)',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Yeniden Olustur
          </button>
        </div>
      ) : null}

      {isAssistant && assistantMetrics.length > 0 ? (
        <div className="mr-6 flex flex-wrap justify-end gap-1.5">
          {assistantMetrics.map((metric) => (
            <div
              key={metric.key}
              className="rounded-full px-2.5 py-1 text-[10px] font-medium"
              style={{
                background: 'var(--chat-muted-card-bg)',
                color: 'var(--color-text-muted)',
                border: '1px solid var(--chat-section-border)',
              }}
            >
              {metric.label}: {metric.value}
            </div>
          ))}
        </div>
      ) : null}

      {isAssistant ? (
        <>
          <CostCard meta={msg.meta} />
          <ContextUsageCard meta={msg.meta} fallbackContextLength={fallbackContextLength} />
        </>
      ) : null}
    </div>
  );
}

export default memo(MessageBubble, (prev, next) =>
  prev.msg === next.msg &&
  prev.assistantLabel === next.assistantLabel &&
  prev.fallbackContextLength === next.fallbackContextLength &&
  prev.onApplyOption === next.onApplyOption &&
  prev.applyDisabled === next.applyDisabled &&
  prev.onRetry === next.onRetry,
);

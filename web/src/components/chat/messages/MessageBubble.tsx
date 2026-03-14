import { memo } from 'react';
import type { ChatMessage } from '../../../hooks/useChat';
import type { SuggestionOption } from '../suggestionUtils';
import { getAssistantMetrics, readMetaNumber } from '../chatUtils';
import ToolResultCard from './ToolResultCard';
import SuggestionSavedCard from './SuggestionSavedCard';
import ThinkingBlock from './ThinkingBlock';
import AssistantMessageContent from './AssistantContent';
import ContextUsageCard from './ContextUsageCard';

export function getRoleMeta(role: ChatMessage['role'], assistantLabel: string) {
  if (role === 'user') return { label: 'Sen', color: '#c7d2fe' };
  if (role === 'assistant') return { label: assistantLabel, color: 'var(--color-text-muted)' };
  return { label: 'Akis', color: 'var(--color-text-muted)' };
}

function MessageBubble({
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
            className="rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed shadow-sm"
            style={{
              background: isUser
                ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.22), rgba(79, 70, 229, 0.18))'
                : isSystem
                  ? 'rgba(148, 163, 184, 0.08)'
                  : 'linear-gradient(160deg, rgba(30,41,59,0.66), rgba(15,23,42,0.7))',
              border: isSystem
                ? 'none'
                : `1px solid ${isUser ? 'rgba(99, 102, 241, 0.35)' : 'rgba(148, 163, 184, 0.22)'}`,
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

export default memo(MessageBubble, (prev, next) =>
  prev.msg.content === next.msg.content &&
  prev.msg.role === next.msg.role &&
  (prev.msg.thinking?.length ?? 0) === (next.msg.thinking?.length ?? 0) &&
  prev.assistantLabel === next.assistantLabel &&
  prev.applyDisabled === next.applyDisabled,
);

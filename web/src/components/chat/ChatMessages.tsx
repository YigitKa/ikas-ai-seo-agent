import { useEffect, useMemo, useRef, useState } from 'react';
import { Virtuoso, type VirtuosoHandle } from 'react-virtuoso';
import type { Product, SeoScore } from '../../types';
import type { ChatMessage as ChatMessageType } from '../../hooks/useChat';
import { MessageBubble, type SuggestionOption } from './ChatMessage';
import SeoScoreChatMessage from './SeoScoreChatMessage';
import { StarterStateCard } from './StarterStateCard';
import { STARTER_PROMPTS } from './chatPanelConstants';
import type { StarterPrompt } from './promptParams';
import { formatDuration } from './chatUtils';

type ChatListItem =
  | {
    key: string;
    kind: 'score';
    score: SeoScore;
    productId: string;
  }
  | {
    key: string;
    kind: 'starter';
  }
  | {
    key: string;
    kind: 'message';
    message: ChatMessageType;
    messageIndex: number;
  }
  | {
    key: string;
    kind: 'loading';
  };

interface ChatMessagesProps {
  score?: SeoScore | null;
  product?: Product | null;
  productId?: string;
  showStarterState: boolean;
  isLoading: boolean;
  isInspectingProduct: boolean;
  isAutoIntroActive: boolean;
  messages: ChatMessageType[];
  assistantLabel: string;
  liveContextLength: number | null;
  liveElapsedSeconds: number;
  /** Override default starter prompts (e.g. store-level prompts on home page). */
  starterPrompts?: StarterPrompt[];
  onStarterPrompt: (prompt: StarterPrompt) => void;
  onApplyOption: (option: SuggestionOption, index: number) => void;
  onRetry: () => void;
}

function LoadingBubble({
  isLoading,
  isInspectingProduct,
  isAutoIntroActive,
  assistantLabel,
  liveElapsedSeconds,
}: {
  isLoading: boolean;
  isInspectingProduct: boolean;
  isAutoIntroActive: boolean;
  assistantLabel: string;
  liveElapsedSeconds: number;
}) {
  if (!isLoading && !isInspectingProduct) {
    return null;
  }

  return (
    <div
      className="mr-6 rounded-2xl px-4 py-3"
      style={{
        background: 'linear-gradient(180deg, var(--surface-raised), var(--surface-panel))',
        border: '1px solid var(--color-border-subtle)',
      }}
    >
      <div className="flex items-center gap-2">
        <div className="flex gap-1">
          <span
            className="typing-dot h-1.5 w-1.5 rounded-full"
            style={{ background: 'var(--color-primary-light)' }}
          />
          <span
            className="typing-dot h-1.5 w-1.5 rounded-full"
            style={{ background: 'var(--color-primary-light)' }}
          />
          <span
            className="typing-dot h-1.5 w-1.5 rounded-full"
            style={{ background: 'var(--color-primary-light)' }}
          />
        </div>
        <span
          className="text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {isAutoIntroActive
            ? 'Asistan urunu inceliyor...'
            : `${assistantLabel} dusunuyor...`}
        </span>
      </div>
      {isLoading && (
        <div
          className="mt-2 text-[11px]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Sure: {formatDuration(liveElapsedSeconds)}
        </div>
      )}
    </div>
  );
}

export function ChatMessages({
  score,
  product,
  productId,
  showStarterState,
  isLoading,
  isInspectingProduct,
  isAutoIntroActive,
  messages,
  assistantLabel,
  liveContextLength,
  liveElapsedSeconds,
  starterPrompts: starterPromptsOverride,
  onStarterPrompt,
  onApplyOption,
  onRetry,
}: ChatMessagesProps) {
  const virtuosoRef = useRef<VirtuosoHandle | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const listItems = useMemo<ChatListItem[]>(() => {
    const nextItems: ChatListItem[] = [];

    if (score && productId) {
      nextItems.push({
        key: `score-${productId}`,
        kind: 'score',
        score,
        productId,
      });
    }

    if (showStarterState) {
      nextItems.push({
        key: 'starter-state',
        kind: 'starter',
      });
    }

    messages.forEach((message, index) => {
      nextItems.push({
        key: message.id,
        kind: 'message',
        message,
        messageIndex: index,
      });
    });

    if (isLoading || isInspectingProduct) {
      nextItems.push({
        key: 'loading-indicator',
        kind: 'loading',
      });
    }

    return nextItems;
  }, [isInspectingProduct, isLoading, messages, productId, score, showStarterState]);

  const lastLiveMessageSignature = useMemo(() => {
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage) {
      return 'empty';
    }

    return [
      lastMessage.id,
      lastMessage.content.length,
      lastMessage.thinking?.length ?? 0,
      lastMessage.toolResults?.length ?? 0,
      lastMessage.suggestionSaved ? 'saved' : 'plain',
    ].join(':');
  }, [messages]);

  useEffect(() => {
    if ((!isLoading && !isInspectingProduct) || !isAtBottom) {
      return;
    }

    const rafId = window.requestAnimationFrame(() => {
      virtuosoRef.current?.autoscrollToBottom();
    });

    return () => window.cancelAnimationFrame(rafId);
  }, [isAtBottom, isInspectingProduct, isLoading, lastLiveMessageSignature]);

  return (
    <div className="flex-1 overflow-hidden">
      <Virtuoso
        ref={virtuosoRef}
        data={listItems}
        className="h-full"
        followOutput={(atBottom) => {
          if (!atBottom) {
            return false;
          }
          return isLoading || isInspectingProduct ? 'auto' : 'smooth';
        }}
        atBottomThreshold={32}
        atBottomStateChange={setIsAtBottom}
        computeItemKey={(_, item) => item.key}
        defaultItemHeight={148}
        overscan={{ main: 480, reverse: 240 }}
        increaseViewportBy={{ top: 240, bottom: 360 }}
        components={{
          Header: () => <div className="h-2" />,
          Footer: () => <div className="h-2" />,
        }}
        itemContent={(_, item) => (
          <div className="px-2 pb-2 last:pb-0 sm:px-3">
            {item.kind === 'score' ? (
              <SeoScoreChatMessage score={item.score} product={product} />
            ) : null}

            {item.kind === 'starter' ? (
              <StarterStateCard
                prompts={starterPromptsOverride ?? STARTER_PROMPTS}
                onPromptClick={onStarterPrompt}
                disabled={isLoading}
              />
            ) : null}

            {item.kind === 'message' ? (
              <MessageBubble
                msg={item.message}
                assistantLabel={assistantLabel}
                fallbackContextLength={liveContextLength}
                onApplyOption={onApplyOption}
                onRetry={item.messageIndex === messages.length - 1 ? onRetry : undefined}
                applyDisabled={isLoading}
              />
            ) : null}

            {item.kind === 'loading' ? (
              <LoadingBubble
                isLoading={isLoading}
                isInspectingProduct={isInspectingProduct}
                isAutoIntroActive={isAutoIntroActive}
                assistantLabel={assistantLabel}
                liveElapsedSeconds={liveElapsedSeconds}
              />
            ) : null}
          </div>
        )}
      />
    </div>
  );
}

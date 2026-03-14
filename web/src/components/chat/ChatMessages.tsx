import type { RefObject } from "react";
import type { SeoScore } from "../../types";
import type { ChatMessage as ChatMessageType } from "../../hooks/useChat";
import { MessageBubble, type SuggestionOption } from "./ChatMessage";
import SeoScoreChatMessage from "./SeoScoreChatMessage";
import { StarterStateCard } from "./StarterStateCard";
import { STARTER_PROMPTS } from "./chatPanelConstants";
import type { StarterPrompt } from "./promptParams";
import { formatDuration } from "./chatUtils";

interface ChatMessagesProps {
  scrollRef: RefObject<HTMLDivElement | null>;
  score?: SeoScore | null;
  productId?: string;
  showStarterState: boolean;
  isLoading: boolean;
  isInspectingProduct: boolean;
  isAutoIntroActive: boolean;
  messages: ChatMessageType[];
  assistantLabel: string;
  liveContextLength: number | null;
  liveElapsedSeconds: number;
  onStarterPrompt: (prompt: StarterPrompt) => void;
  onApplyOption: (option: SuggestionOption, index: number) => void;
}

export function ChatMessages({
  scrollRef,
  score,
  productId,
  showStarterState,
  isLoading,
  isInspectingProduct,
  isAutoIntroActive,
  messages,
  assistantLabel,
  liveContextLength,
  liveElapsedSeconds,
  onStarterPrompt,
  onApplyOption,
}: ChatMessagesProps) {
  return (
    <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-4">
      {/* Score analysis -- shown as the app's first message before LLM */}
      {score && productId && (
        <SeoScoreChatMessage key={`score-${productId}`} score={score} />
      )}

      {showStarterState && (
        <StarterStateCard
          prompts={STARTER_PROMPTS}
          onPromptClick={onStarterPrompt}
          disabled={isLoading}
        />
      )}

      {messages.map((msg, i) => (
        <MessageBubble
          key={i}
          msg={msg}
          assistantLabel={assistantLabel}
          fallbackContextLength={liveContextLength}
          onApplyOption={onApplyOption}
          applyDisabled={isLoading}
        />
      ))}

      {(isLoading || isInspectingProduct) && (
        <div
          className="mr-6 rounded-2xl px-4 py-3"
          style={{
            background: "linear-gradient(180deg, rgba(30,41,59,0.75), rgba(15,23,42,0.8))",
            border: "1px solid rgba(148,163,184,0.2)",
          }}
        >
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              <span
                className="typing-dot h-1.5 w-1.5 rounded-full"
                style={{ background: "var(--color-primary-light)" }}
              />
              <span
                className="typing-dot h-1.5 w-1.5 rounded-full"
                style={{ background: "var(--color-primary-light)" }}
              />
              <span
                className="typing-dot h-1.5 w-1.5 rounded-full"
                style={{ background: "var(--color-primary-light)" }}
              />
            </div>
            <span
              className="text-xs"
              style={{ color: "var(--color-text-muted)" }}
            >
              {isAutoIntroActive
                ? "Asistan urunu inceliyor..."
                : `${assistantLabel} dusunuyor...`}
            </span>
          </div>
          {isLoading && (
            <div
              className="mt-2 text-[11px]"
              style={{ color: "var(--color-text-secondary)" }}
            >
              Sure: {formatDuration(liveElapsedSeconds)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

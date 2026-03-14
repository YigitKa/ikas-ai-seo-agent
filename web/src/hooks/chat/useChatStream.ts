import { useCallback, useRef } from 'react';
import type { ChatResponseMeta, ChatWsMessage, SeoSuggestion } from '../../types';
import type { ChatMessage } from '../useChat';

type BufferedChunk = { type: 'content' | 'thinking'; text: string };

function estimateChunkTokens(text: string): number {
  const normalized = text.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return 0;
  }

  // Quick approximation for live UX: ~1 token per 4 chars.
  return Math.max(1, Math.round(normalized.length / 4));
}

interface UseChatStreamDeps {
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  finishPendingRequest: () => number | undefined;
  addTokenEstimate: (tokens: number) => void;
  setPendingSuggestion: React.Dispatch<React.SetStateAction<SeoSuggestion | null>>;
}

export function useChatStream(deps: UseChatStreamDeps) {
  const { setMessages, finishPendingRequest, addTokenEstimate, setPendingSuggestion } = deps;

  const chunkBufferRef = useRef<BufferedChunk[]>([]);
  const rafIdRef = useRef<number | null>(null);

  // ---------------------------------------------------------------------------
  // RAF-buffered chunk flushing
  // ---------------------------------------------------------------------------

  const flushChunkBuffer = useCallback(() => {
    rafIdRef.current = null;
    const buffer = chunkBufferRef.current;
    if (buffer.length === 0) return;
    chunkBufferRef.current = [];

    setMessages((prev) => {
      const next = [...prev];
      let lastMessage = next[next.length - 1];

      for (const chunk of buffer) {
        if (chunk.type === 'content') {
          if (lastMessage?.role === 'assistant') {
            lastMessage = {
              ...lastMessage,
              content: `${lastMessage.content}${chunk.text}`,
            };
            next[next.length - 1] = lastMessage;
          } else {
            lastMessage = { role: 'assistant', content: chunk.text };
            next.push(lastMessage);
          }
        } else {
          // thinking chunk
          if (lastMessage?.role === 'assistant') {
            lastMessage = {
              ...lastMessage,
              thinking: `${lastMessage.thinking ?? ''}${chunk.text}`,
            };
            next[next.length - 1] = lastMessage;
          } else {
            lastMessage = { role: 'assistant', content: '', thinking: chunk.text };
            next.push(lastMessage);
          }
        }
      }

      return next;
    });
  }, [setMessages]);

  const scheduleFlush = useCallback(() => {
    if (rafIdRef.current === null) {
      rafIdRef.current = requestAnimationFrame(flushChunkBuffer);
    }
  }, [flushChunkBuffer]);

  const appendAssistantChunk = useCallback((chunk: string) => {
    if (!chunk) return;
    chunkBufferRef.current.push({ type: 'content', text: chunk });
    addTokenEstimate(estimateChunkTokens(chunk));
    scheduleFlush();
  }, [scheduleFlush, addTokenEstimate]);

  const appendThinkingChunk = useCallback((chunk: string) => {
    if (!chunk) return;
    chunkBufferRef.current.push({ type: 'thinking', text: chunk });
    addTokenEstimate(estimateChunkTokens(chunk));
    scheduleFlush();
  }, [scheduleFlush, addTokenEstimate]);

  const finalizeAssistantMessage = useCallback((data: ChatWsMessage) => {
    // Cancel any pending RAF flush -- the finalized payload replaces streamed state
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    chunkBufferRef.current = [];

    const elapsedSeconds = finishPendingRequest();
    const meta: ChatResponseMeta = {
      ...(data.meta ?? {}),
      ...(typeof elapsedSeconds === 'number' ? { elapsed_seconds: elapsedSeconds } : {}),
    };
    setPendingSuggestion(data.pending_suggestion ?? null);

    setMessages((prev) => {
      const next = [...prev];
      const finalizedMessage: ChatMessage = {
        role: 'assistant',
        content: typeof data.content === 'string' ? data.content : '',
        thinking: data.thinking,
        toolResults: data.tool_results,
        meta,
        suggestionSaved: data.suggestion_saved,
        pendingSuggestion: data.pending_suggestion,
      };
      const lastMessage = next[next.length - 1];

      if (lastMessage?.role === 'assistant') {
        next[next.length - 1] = {
          ...lastMessage,
          ...finalizedMessage,
          content: typeof data.content === 'string' ? data.content : lastMessage.content,
        };
        return next;
      }

      next.push(finalizedMessage);
      return next;
    });
  }, [finishPendingRequest, setMessages, setPendingSuggestion]);

  const cleanup = useCallback(() => {
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    chunkBufferRef.current = [];
  }, []);

  return {
    appendAssistantChunk,
    appendThinkingChunk,
    finalizeAssistantMessage,
    cleanup,
  };
}

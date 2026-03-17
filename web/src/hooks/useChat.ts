import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatResponseMeta, SeoSuggestion, SuggestionSavedInfo, ToolResult } from '../types';
import { useChatStatus } from './chat/useChatStatus';
import { useChatStream } from './chat/useChatStream';
import { useChatAutoIntro } from './chat/useChatAutoIntro';
import { useChatWebSocket } from './chat/useChatWebSocket';

export type { MCPState } from './chat/useChatStatus';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  thinking?: string;
  toolResults?: ToolResult[];
  meta?: ChatResponseMeta;
  suggestionSaved?: SuggestionSavedInfo;
  pendingSuggestion?: SeoSuggestion | null;
}

export interface ChatProductContext {
  id?: string;
  name?: string;
  category?: string | null;
  score?: number | null;
  assistantLabel?: string;
}

export interface UseChatOptions {
  productContext?: ChatProductContext;
  onProductUpdated?: () => void;
}

export function useChat(productContext?: ChatProductContext, onProductUpdated?: () => void) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const productContextRef = useRef(productContext);
  const activeProductIdRef = useRef<string | undefined>(undefined);

  productContextRef.current = productContext;

  // --- Status sub-hook ---
  const status = useChatStatus();

  const resetToContextIntro = useCallback(() => {
    setMessages([]);
    status.setPendingSuggestion(null);
  }, [status.setPendingSuggestion]);

  // --- Stream sub-hook ---
  const stream = useChatStream({
    setMessages,
    finishPendingRequest: status.finishPendingRequest,
    addTokenEstimate: status.addTokenEstimate,
    setPendingSuggestion: status.setPendingSuggestion,
  });

  // --- Auto-intro sub-hook (needs wsRef from websocket, but websocket needs auto-intro) ---
  // We use a shared wsRef that the websocket hook populates
  const sharedWsRef = useRef<WebSocket | null>(null);

  const autoIntro = useChatAutoIntro({
    productContextRef,
    wsRef: sharedWsRef,
    startPendingRequest: status.startPendingRequest,
  });

  // --- WebSocket sub-hook ---
  const ws = useChatWebSocket({
    productContextRef,
    pendingSinceRef: status.pendingSinceRef,
    startPendingRequest: status.startPendingRequest,
    finishPendingRequest: status.finishPendingRequest,
    incrementChunkCount: status.incrementChunkCount,
    setMcpState: status.setMcpState,
    setPendingSuggestion: status.setPendingSuggestion,
    setMessages,
    appendAssistantChunk: stream.appendAssistantChunk,
    appendThinkingChunk: stream.appendThinkingChunk,
    finalizeAssistantMessage: stream.finalizeAssistantMessage,
    clearActiveAutoIntro: autoIntro.clearActiveAutoIntro,
    clearAutoIntro: autoIntro.clearAutoIntro,
    sendHiddenAutoIntro: autoIntro.sendHiddenAutoIntro,
    resetToContextIntro,
    onProductUpdated,
  });

  // Keep the shared wsRef in sync with the websocket hook's ref
  useEffect(() => {
    sharedWsRef.current = ws.wsRef.current;
  });

  // --- Product context switch effect ---
  useEffect(() => {
    const nextProductId = productContext?.id;
    const prevProductId = activeProductIdRef.current;

    if (!nextProductId) {
      activeProductIdRef.current = undefined;
      autoIntro.clearAutoIntro();
      setMessages([]);
      status.setPendingSuggestion(null);
      return;
    }

    if (prevProductId === nextProductId) {
      return;
    }

    activeProductIdRef.current = nextProductId;
    autoIntro.queueAutoIntro(nextProductId);

    if (ws.wsRef.current?.readyState === WebSocket.OPEN) {
      ws.clearReasonRef.current = 'switch';
      ws.wsRef.current.send(JSON.stringify({ action: 'clear' }));
      ws.wsRef.current.send(JSON.stringify({ action: 'set_context', product_id: nextProductId }));
    }

    resetToContextIntro();
  }, [
    productContext?.id,
    productContext?.name,
    productContext?.category,
    productContext?.score,
    productContext?.assistantLabel,
    autoIntro.clearAutoIntro,
    autoIntro.queueAutoIntro,
    resetToContextIntro,
    ws.wsRef,
    ws.clearReasonRef,
    status.setPendingSuggestion,
  ]);

  // Clean up RAF on unmount
  useEffect(() => {
    return () => {
      stream.cleanup();
    };
  }, [stream.cleanup]);

  const addLocalMessage = useCallback(
    (msg: ChatMessage) => {
      setMessages((prev) => [...prev, msg]);
    },
    [],
  );

  return {
    messages,
    isLoading: status.isLoading,
    isReconnecting: ws.isReconnecting,
    isAutoIntroActive: autoIntro.autoIntroProductId === productContext?.id,
    pendingSince: status.pendingSince,
    liveChunkCount: status.liveChunkCount,
    liveTokenEstimate: status.liveTokenEstimate,
    pendingSuggestion: status.pendingSuggestion,
    mcpState: status.mcpState,
    sendMessage: ws.sendMessage,
    retryLastMessage: ws.retryLastMessage,
    addLocalMessage,
    cancelMessage: ws.cancelMessage,
    clearHistory: ws.clearHistory,
    connect: ws.connect,
    disconnect: ws.disconnect,
  };
}

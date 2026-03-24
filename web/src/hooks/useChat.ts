import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatResponseMeta, SeoSuggestion, SuggestionSavedInfo, ToolResult } from '../types';
import { useChatStatus } from './chat/useChatStatus';
import { useChatStream } from './chat/useChatStream';
import { useChatAutoIntro } from './chat/useChatAutoIntro';
import { useChatWebSocket } from './chat/useChatWebSocket';
import {
  loadHistory,
  saveHistory,
  clearHistory as clearStoredHistory,
  hasHistory,
  markRead,
} from './chat/chatHistory';

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

  // Keep a ref in sync so callbacks/effects can read the latest messages without
  // adding `messages` to every dependency array (which would cause unnecessary
  // re-runs during high-frequency streaming).
  const messagesRef = useRef<ChatMessage[]>([]);
  useEffect(() => {
    messagesRef.current = messages;
  });

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

  // --- Save history when a response finishes loading ---
  const prevIsLoadingRef = useRef(false);
  useEffect(() => {
    const wasLoading = prevIsLoadingRef.current;
    prevIsLoadingRef.current = status.isLoading;

    if (wasLoading && !status.isLoading && activeProductIdRef.current) {
      saveHistory(activeProductIdRef.current, messagesRef.current);
    }
  }, [status.isLoading]);

  // --- Save history before the page unloads (e.g. tab close / refresh) ---
  useEffect(() => {
    const handleBeforeUnload = () => {
      const productId = activeProductIdRef.current;
      if (productId && messagesRef.current.length > 0) {
        saveHistory(productId, messagesRef.current);
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

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

    // Persist the outgoing product's messages before clearing them
    if (prevProductId && messagesRef.current.length > 0) {
      saveHistory(prevProductId, messagesRef.current);
    }

    activeProductIdRef.current = nextProductId;

    if (ws.wsRef.current?.readyState === WebSocket.OPEN) {
      ws.clearReasonRef.current = 'switch';
      ws.wsRef.current.send(JSON.stringify({ action: 'clear' }));
      ws.wsRef.current.send(JSON.stringify({ action: 'set_context', product_id: nextProductId }));
    }

    // Restore stored history OR start with a clean slate + auto-intro
    const stored = loadHistory(nextProductId);
    if (stored.length > 0) {
      setMessages(stored);
      status.setPendingSuggestion(null);
      // Don't queue auto-intro — the user already has a conversation for this product.
      // (sendHiddenAutoIntro will be a no-op because nothing is queued.)
    } else {
      resetToContextIntro();
      autoIntro.queueAutoIntro(nextProductId);
    }

    // Mark this product's history as read now that the user is viewing it
    markRead(nextProductId);
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

  // --- clearHistory: also wipes localStorage for the active product ---
  const clearHistory = useCallback(() => {
    if (activeProductIdRef.current) {
      clearStoredHistory(activeProductIdRef.current);
    }
    ws.clearHistory();
  }, [ws.clearHistory]);

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
    clearHistory,
    connect: ws.connect,
    disconnect: ws.disconnect,
  };
}

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatWsMessage, SeoSuggestion } from '../../types';
import type { ChatMessage } from '../useChat';
import type { MCPState } from './useChatStatus';

const MAX_RECONNECT_ATTEMPTS = 8;
const BASE_RECONNECT_DELAY_MS = 1000;

interface UseChatWebSocketDeps {
  productContextRef: React.RefObject<{ id?: string } | undefined>;
  pendingSinceRef: React.RefObject<number | null>;

  // Status callbacks
  startPendingRequest: () => void;
  finishPendingRequest: () => number | undefined;
  incrementChunkCount: () => void;
  setMcpState: React.Dispatch<React.SetStateAction<MCPState>>;
  setPendingSuggestion: React.Dispatch<React.SetStateAction<SeoSuggestion | null>>;
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;

  // Stream callbacks
  appendAssistantChunk: (chunk: string) => void;
  appendThinkingChunk: (chunk: string) => void;
  finalizeAssistantMessage: (data: ChatWsMessage) => void;

  // Auto-intro callbacks
  clearActiveAutoIntro: () => void;
  clearAutoIntro: () => void;
  sendHiddenAutoIntro: (productId: string) => void;

  // Message reset
  resetToContextIntro: () => void;

  // Product update notification
  onProductUpdated?: () => void;
}

export function useChatWebSocket(deps: UseChatWebSocketDeps) {
  const {
    productContextRef,
    pendingSinceRef,
    startPendingRequest,
    finishPendingRequest,
    incrementChunkCount,
    setMcpState,
    setPendingSuggestion,
    setMessages,
    appendAssistantChunk,
    appendThinkingChunk,
    finalizeAssistantMessage,
    clearActiveAutoIntro,
    clearAutoIntro,
    sendHiddenAutoIntro,
    resetToContextIntro,
    onProductUpdated,
  } = deps;

  const [isReconnecting, setIsReconnecting] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const clearReasonRef = useRef<'switch' | 'clear'>('clear');
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalDisconnectRef = useRef(false);
  const lastSentPayloadRef = useRef<{ message: string; productId: string; hidden: boolean } | null>(null);

  // Forward-ref so scheduleReconnect can call connect without a circular dep
  const connectRef = useRef<() => void>(() => {});

  // ---------------------------------------------------------------------------
  // Exponential-backoff auto-reconnect
  // ---------------------------------------------------------------------------

  const scheduleReconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      setIsReconnecting(false);
      return;
    }

    const delay = Math.min(
      BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttemptsRef.current),
      60_000,
    );
    reconnectAttemptsRef.current += 1;
    setIsReconnecting(true);

    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connectRef.current();
    }, delay);
  }, []);

  // ---------------------------------------------------------------------------
  // WebSocket connect
  // ---------------------------------------------------------------------------

  const connect = useCallback(() => {
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    intentionalDisconnectRef.current = false;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;
      setIsReconnecting(false);

      const productId = productContextRef.current?.id;
      if (productId) {
        ws.send(JSON.stringify({ action: 'set_context', product_id: productId }));
      }
    };

    ws.onmessage = (event) => {
      const data: ChatWsMessage = JSON.parse(event.data);
      if (data.type === 'chunk' || data.type === 'thinking_chunk') {
        incrementChunkCount();
      }

      switch (data.type) {
        case 'chunk':
          appendAssistantChunk(data.content || '');
          break;

        case 'thinking_chunk':
          appendThinkingChunk(data.content || '');
          break;

        case 'response':
        case 'response_done': {
          clearActiveAutoIntro();
          finalizeAssistantMessage(data);
          if ((data as unknown as Record<string, unknown>).product_updated && onProductUpdated) {
            onProductUpdated();
          }
          break;
        }

        case 'error':
          finishPendingRequest();
          clearActiveAutoIntro();
          setMessages((prev) => [
            ...prev,
            { role: 'system', content: data.content || data.message || 'Hata' },
          ]);
          break;

        case 'cancelled':
          finishPendingRequest();
          clearActiveAutoIntro();
          setMessages((prev) => [
            ...prev,
            { role: 'system', content: data.message || 'Istek durduruldu.' },
          ]);
          break;

        case 'thinking':
          break;

        case 'mcp_status':
          setMcpState({
            hasToken: data.has_token ?? false,
            initialized: data.initialized ?? false,
            toolCount: data.tool_count ?? 0,
            tools: data.tools ?? [],
            message: data.message || '',
          });
          break;

        case 'context_set':
          setPendingSuggestion(data.pending_suggestion ?? null);
          if (data.product_id) {
            sendHiddenAutoIntro(data.product_id);
          }
          break;

        case 'cleared':
          finishPendingRequest();
          clearActiveAutoIntro();
          resetToContextIntro();
          clearReasonRef.current = 'clear';
          break;
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      finishPendingRequest();
      clearAutoIntro();

      if (!intentionalDisconnectRef.current) {
        scheduleReconnect();
      }
    };
  }, [
    appendAssistantChunk,
    appendThinkingChunk,
    clearActiveAutoIntro,
    clearAutoIntro,
    finalizeAssistantMessage,
    finishPendingRequest,
    incrementChunkCount,
    productContextRef,
    onProductUpdated,
    resetToContextIntro,
    scheduleReconnect,
    sendHiddenAutoIntro,
    setMessages,
    setMcpState,
    setPendingSuggestion,
  ]);

  // Keep the forward-ref up to date after every render so scheduleReconnect
  // always calls the latest version of connect.
  useEffect(() => {
    connectRef.current = connect;
  });

  // Clean up reconnect timer on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, []);

  const sendMessage = useCallback(
    (message: string, options?: { hidden?: boolean }) => {
      const productId = productContextRef.current?.id;
      if (!productId) return;

      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
        window.setTimeout(() => sendMessage(message, options), 500);
        return;
      }

      if (!options?.hidden) {
        setMessages((prev) => [...prev, { role: 'user', content: message }]);
      }
      lastSentPayloadRef.current = { message, productId, hidden: !!options?.hidden };
      startPendingRequest();
      wsRef.current.send(
        JSON.stringify({ action: 'message', message, product_id: productId }),
      );
    },
    [connect, startPendingRequest, productContextRef, setMessages],
  );

  const retryLastMessage = useCallback(() => {
    const payload = lastSentPayloadRef.current;
    if (!payload) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    // Remove the failed assistant message (last message if it's from assistant)
    setMessages((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].role === 'assistant') {
        return prev.slice(0, -1);
      }
      return prev;
    });

    startPendingRequest();
    wsRef.current.send(
      JSON.stringify({ action: 'message', message: payload.message, product_id: payload.productId }),
    );
  }, [startPendingRequest, setMessages]);

  const clearHistory = useCallback(() => {
    clearAutoIntro();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      clearReasonRef.current = 'clear';
      wsRef.current.send(JSON.stringify({ action: 'clear' }));
      return;
    }
    resetToContextIntro();
  }, [clearAutoIntro, resetToContextIntro]);

  const cancelMessage = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN || pendingSinceRef.current === null) {
      return;
    }
    wsRef.current.send(JSON.stringify({ action: 'cancel' }));
  }, [pendingSinceRef]);

  const disconnect = useCallback(() => {
    intentionalDisconnectRef.current = true;
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectAttemptsRef.current = 0;
    setIsReconnecting(false);
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return {
    wsRef,
    isReconnecting,
    clearReasonRef,
    connect,
    disconnect,
    sendMessage,
    retryLastMessage,
    cancelMessage,
    clearHistory,
  };
}

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatResponseMeta, ChatWsMessage, MCPToolInfo, SuggestionSavedInfo, ToolResult } from '../types';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  thinking?: string;
  toolResults?: ToolResult[];
  meta?: ChatResponseMeta;
  suggestionSaved?: SuggestionSavedInfo;
}

export interface MCPState {
  hasToken: boolean;
  initialized: boolean;
  toolCount: number;
  tools: MCPToolInfo[];
  message: string;
}

export interface ChatProductContext {
  id?: string;
  name?: string;
  category?: string | null;
  score?: number | null;
  assistantLabel?: string;
}

interface SendMessageOptions {
  hidden?: boolean;
}

const AUTO_PRODUCT_OVERVIEW_PROMPT =
  'Bu urunun SEO durumunu incele ve ilk tespitlerini bir asistan gibi proaktif bir dille bana sun.';

const MAX_RECONNECT_ATTEMPTS = 8;
const BASE_RECONNECT_DELAY_MS = 1000;

type BufferedChunk = { type: 'content' | 'thinking'; text: string };

export function useChat(productContext?: ChatProductContext) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [pendingSince, setPendingSince] = useState<number | null>(null);
  const [liveChunkCount, setLiveChunkCount] = useState(0);
  const [autoIntroProductId, setAutoIntroProductId] = useState<string | null>(null);
  const [mcpState, setMcpState] = useState<MCPState>({
    hasToken: false,
    initialized: false,
    toolCount: 0,
    tools: [],
    message: '',
  });

  const wsRef = useRef<WebSocket | null>(null);
  const productContextRef = useRef(productContext);
  const activeProductIdRef = useRef<string | undefined>(undefined);
  const clearReasonRef = useRef<'switch' | 'clear'>('clear');
  const pendingSinceRef = useRef<number | null>(null);
  const queuedAutoIntroProductIdRef = useRef<string | null>(null);
  const activeAutoIntroProductIdRef = useRef<string | null>(null);

  // RAF buffer for stream chunks — avoids calling setMessages on every single chunk
  const chunkBufferRef = useRef<BufferedChunk[]>([]);
  const rafIdRef = useRef<number | null>(null);

  // Reconnect state
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalDisconnectRef = useRef(false);

  // Forward-ref so scheduleReconnect can call connect without a circular dep
  const connectRef = useRef<() => void>(() => {});

  productContextRef.current = productContext;

  const syncAutoIntroState = useCallback(() => {
    setAutoIntroProductId(
      activeAutoIntroProductIdRef.current ?? queuedAutoIntroProductIdRef.current,
    );
  }, []);

  const queueAutoIntro = useCallback((productId?: string) => {
    queuedAutoIntroProductIdRef.current = productId ?? null;
    activeAutoIntroProductIdRef.current = null;
    syncAutoIntroState();
  }, [syncAutoIntroState]);

  const clearAutoIntro = useCallback(() => {
    queuedAutoIntroProductIdRef.current = null;
    activeAutoIntroProductIdRef.current = null;
    syncAutoIntroState();
  }, [syncAutoIntroState]);

  const clearActiveAutoIntro = useCallback(() => {
    if (activeAutoIntroProductIdRef.current === null) {
      return;
    }

    activeAutoIntroProductIdRef.current = null;
    syncAutoIntroState();
  }, [syncAutoIntroState]);

  const startPendingRequest = useCallback(() => {
    const startedAt = performance.now();
    pendingSinceRef.current = startedAt;
    setPendingSince(startedAt);
    setLiveChunkCount(0);
    setIsLoading(true);
  }, []);

  const finishPendingRequest = useCallback(() => {
    const startedAt = pendingSinceRef.current;
    pendingSinceRef.current = null;
    setPendingSince(null);
    setIsLoading(false);
    if (startedAt === null) {
      return undefined;
    }
    return (performance.now() - startedAt) / 1000;
  }, []);

  const resetToContextIntro = useCallback(
    () => {
      setMessages([]);
    },
    [],
  );

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
  }, []);

  const scheduleFlush = useCallback(() => {
    if (rafIdRef.current === null) {
      rafIdRef.current = requestAnimationFrame(flushChunkBuffer);
    }
  }, [flushChunkBuffer]);

  const appendAssistantChunk = useCallback((chunk: string) => {
    if (!chunk) return;
    chunkBufferRef.current.push({ type: 'content', text: chunk });
    scheduleFlush();
  }, [scheduleFlush]);

  const appendThinkingChunk = useCallback((chunk: string) => {
    if (!chunk) return;
    chunkBufferRef.current.push({ type: 'thinking', text: chunk });
    scheduleFlush();
  }, [scheduleFlush]);

  const finalizeAssistantMessage = useCallback((data: ChatWsMessage) => {
    // Cancel any pending RAF flush — the finalized payload replaces streamed state
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

    setMessages((prev) => {
      const next = [...prev];
      const finalizedMessage: ChatMessage = {
        role: 'assistant',
        content: typeof data.content === 'string' ? data.content : '',
        thinking: data.thinking,
        toolResults: data.tool_results,
        meta,
        suggestionSaved: data.suggestion_saved,
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
  }, [finishPendingRequest]);

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

  const sendHiddenAutoIntro = useCallback((productId: string) => {
    if (queuedAutoIntroProductIdRef.current !== productId) {
      return;
    }

    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      return;
    }

    const currentProductId = productContextRef.current?.id;
    if (!currentProductId || currentProductId !== productId) {
      queuedAutoIntroProductIdRef.current = null;
      syncAutoIntroState();
      return;
    }

    queuedAutoIntroProductIdRef.current = null;
    activeAutoIntroProductIdRef.current = productId;
    syncAutoIntroState();
    startPendingRequest();
    wsRef.current.send(
      JSON.stringify({
        action: 'message',
        message: AUTO_PRODUCT_OVERVIEW_PROMPT,
        product_id: productId,
      }),
    );
  }, [startPendingRequest, syncAutoIntroState]);

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
        setLiveChunkCount((prev) => prev + 1);
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
    resetToContextIntro,
    scheduleReconnect,
    sendHiddenAutoIntro,
  ]);

  // Keep the forward-ref up to date after every render so scheduleReconnect
  // always calls the latest version of connect.
  useEffect(() => {
    connectRef.current = connect;
  });

  useEffect(() => {
    const nextProductId = productContext?.id;
    const prevProductId = activeProductIdRef.current;

    if (!nextProductId) {
      activeProductIdRef.current = undefined;
      clearAutoIntro();
      setMessages([]);
      return;
    }

    if (prevProductId === nextProductId) {
      return;
    }

    activeProductIdRef.current = nextProductId;
    queueAutoIntro(nextProductId);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      clearReasonRef.current = 'switch';
      wsRef.current.send(JSON.stringify({ action: 'clear' }));
      wsRef.current.send(JSON.stringify({ action: 'set_context', product_id: nextProductId }));
    }

    resetToContextIntro();
  }, [
    productContext?.id,
    productContext?.name,
    productContext?.category,
    productContext?.score,
    productContext?.assistantLabel,
    clearAutoIntro,
    queueAutoIntro,
    resetToContextIntro,
  ]);

  // Clean up RAF and reconnect timer on unmount
  useEffect(() => {
    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, []);

  const sendMessage = useCallback(
    (message: string, options?: SendMessageOptions) => {
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
      startPendingRequest();
      wsRef.current.send(
        JSON.stringify({ action: 'message', message, product_id: productId }),
      );
    },
    [connect, startPendingRequest],
  );

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
  }, []);

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
    messages,
    isLoading,
    isReconnecting,
    isAutoIntroActive: autoIntroProductId === productContext?.id,
    pendingSince,
    liveChunkCount,
    mcpState,
    sendMessage,
    cancelMessage,
    clearHistory,
    connect,
    disconnect,
  };
}

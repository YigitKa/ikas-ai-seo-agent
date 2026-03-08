import { startTransition, useCallback, useEffect, useRef, useState } from 'react';
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

export function useChat(productContext?: ChatProductContext) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingSince, setPendingSince] = useState<number | null>(null);
  const [mcpState, setMcpState] = useState<MCPState>({
    hasToken: false,
    initialized: false,
    toolCount: 0,
    tools: [],
    message: '',
  });
  const wsRef = useRef<WebSocket | null>(null);
  const productContextRef = useRef(productContext);
  const activeProductIdRef = useRef<string | undefined>(productContext?.id);
  const clearReasonRef = useRef<'switch' | 'clear'>('clear');
  const pendingSinceRef = useRef<number | null>(null);
  productContextRef.current = productContext;

  const startPendingRequest = useCallback(() => {
    const startedAt = performance.now();
    pendingSinceRef.current = startedAt;
    setPendingSince(startedAt);
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

  const appendAssistantChunk = useCallback((chunk: string) => {
    if (!chunk) {
      return;
    }

    startTransition(() => {
      setMessages((prev) => {
        const next = [...prev];
        const lastMessage = next[next.length - 1];

        if (lastMessage?.role === 'assistant') {
          next[next.length - 1] = {
            ...lastMessage,
            content: `${lastMessage.content}${chunk}`,
          };
          return next;
        }

        next.push({
          role: 'assistant',
          content: chunk,
        });
        return next;
      });
    });
  }, []);

  const finalizeAssistantMessage = useCallback((data: ChatWsMessage) => {
    const elapsedSeconds = finishPendingRequest();
    const meta: ChatResponseMeta = {
      ...(data.meta ?? {}),
      ...(typeof elapsedSeconds === 'number' ? { elapsed_seconds: elapsedSeconds } : {}),
    };

    startTransition(() => {
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
    });
  }, [finishPendingRequest]);

  const connect = useCallback(() => {
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);
    wsRef.current = ws;

    ws.onopen = () => {
      const productId = productContextRef.current?.id;
      if (productId) {
        ws.send(JSON.stringify({ action: 'set_context', product_id: productId }));
      }
    };

    ws.onmessage = (event) => {
      const data: ChatWsMessage = JSON.parse(event.data);

      switch (data.type) {
        case 'chunk':
          appendAssistantChunk(data.content || '');
          break;

        case 'response':
        case 'response_done': {
          finalizeAssistantMessage(data);
          break;
        }

        case 'error':
          finishPendingRequest();
          setMessages((prev) => [
            ...prev,
            { role: 'system', content: data.content || data.message || 'Hata' },
          ]);
          break;

        case 'cancelled':
          finishPendingRequest();
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
          break;

        case 'cleared':
          finishPendingRequest();
          resetToContextIntro();
          clearReasonRef.current = 'clear';
          break;
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      finishPendingRequest();
    };
  }, [appendAssistantChunk, finalizeAssistantMessage, finishPendingRequest, resetToContextIntro]);

  useEffect(() => {
    const nextProductId = productContext?.id;
    const prevProductId = activeProductIdRef.current;

    if (!nextProductId) {
      activeProductIdRef.current = undefined;
      setMessages([]);
      return;
    }

    if (prevProductId === nextProductId) {
      return;
    }

    activeProductIdRef.current = nextProductId;

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
    resetToContextIntro,
  ]);

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
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      clearReasonRef.current = 'clear';
      wsRef.current.send(JSON.stringify({ action: 'clear' }));
      return;
    }
    resetToContextIntro();
  }, [resetToContextIntro]);

  const cancelMessage = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN || pendingSinceRef.current === null) {
      return;
    }
    wsRef.current.send(JSON.stringify({ action: 'cancel' }));
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return {
    messages,
    isLoading,
    pendingSince,
    mcpState,
    sendMessage,
    cancelMessage,
    clearHistory,
    connect,
    disconnect,
  };
}

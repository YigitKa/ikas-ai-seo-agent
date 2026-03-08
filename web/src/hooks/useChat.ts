import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatWsMessage, MCPToolInfo, ToolResult } from '../types';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  thinking?: string;
  toolResults?: ToolResult[];
  meta?: Record<string, unknown>;
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

function buildContextIntro(
  context?: ChatProductContext,
  reason: 'initial' | 'switch' | 'clear' = 'initial',
): ChatMessage[] {
  if (!context?.id || !context.name) {
    return [];
  }

  const summaryBits = [
    context.category ? `Kategori: ${context.category}` : null,
    typeof context.score === 'number' ? `SEO: ${context.score}/100` : null,
  ].filter(Boolean);

  const lead =
    reason === 'switch'
      ? `Konusma yeni secili urune baglandi: ${context.name}`
      : reason === 'clear'
        ? `Konusma temizlendi. Hala secili urun: ${context.name}`
        : `Secili urun icin sohbet hazir: ${context.name}`;

  const flow =
    `Akis: Sen hedefi belirlersin, ${context.assistantLabel || 'AI modeli'} yorumu ve oneriyi uretir, ikas MCP gerekirse canli magaza verisini getirir.`;

  const summary = summaryBits.length > 0 ? summaryBits.join(' | ') : 'Urun baglami hazir.';

  return [
    { role: 'system', content: lead },
    { role: 'system', content: `${flow} ${summary}` },
  ];
}

export function useChat(productContext?: ChatProductContext) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => buildContextIntro(productContext));
  const [isLoading, setIsLoading] = useState(false);
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
  productContextRef.current = productContext;

  const resetToContextIntro = useCallback(
    (reason: 'initial' | 'switch' | 'clear' = 'initial') => {
      setMessages(buildContextIntro(productContextRef.current, reason));
    },
    [],
  );

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
        case 'response':
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: data.content || '',
              thinking: data.thinking,
              toolResults: data.tool_results,
              meta: data.meta,
            },
          ]);
          setIsLoading(false);
          break;

        case 'error':
          setMessages((prev) => [
            ...prev,
            { role: 'system', content: data.content || data.message || 'Hata' },
          ]);
          setIsLoading(false);
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
          resetToContextIntro(clearReasonRef.current);
          clearReasonRef.current = 'clear';
          break;
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      setIsLoading(false);
    };
  }, [resetToContextIntro]);

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

    resetToContextIntro(prevProductId ? 'switch' : 'initial');
  }, [
    productContext?.id,
    productContext?.name,
    productContext?.category,
    productContext?.score,
    productContext?.assistantLabel,
    resetToContextIntro,
  ]);

  const sendMessage = useCallback(
    (message: string) => {
      const productId = productContextRef.current?.id;
      if (!productId) return;

      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
        window.setTimeout(() => sendMessage(message), 500);
        return;
      }

      setMessages((prev) => [...prev, { role: 'user', content: message }]);
      setIsLoading(true);
      wsRef.current.send(
        JSON.stringify({ action: 'message', message, product_id: productId }),
      );
    },
    [connect],
  );

  const clearHistory = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      clearReasonRef.current = 'clear';
      wsRef.current.send(JSON.stringify({ action: 'clear' }));
      return;
    }
    resetToContextIntro('clear');
  }, [resetToContextIntro]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { messages, isLoading, mcpState, sendMessage, clearHistory, connect, disconnect };
}

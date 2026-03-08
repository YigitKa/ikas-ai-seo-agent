import { useCallback, useRef, useState } from 'react';
import type { ChatWsMessage, ToolResult } from '../types';

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
  message: string;
}

export function useChat(productId?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [mcpState, setMcpState] = useState<MCPState>({
    hasToken: false,
    initialized: false,
    message: '',
  });
  const wsRef = useRef<WebSocket | null>(null);
  const productIdRef = useRef(productId);
  productIdRef.current = productId;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);
    wsRef.current = ws;

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
          // Loading indicator handled by isLoading state
          break;

        case 'mcp_status':
          setMcpState({
            hasToken: true,
            initialized: data.initialized ?? false,
            message: data.message || '',
          });
          if (data.message) {
            setMessages((prev) => [
              ...prev,
              { role: 'system', content: data.message! },
            ]);
          }
          break;

        case 'context_set':
          break;

        case 'cleared':
          setMessages([]);
          break;
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      setIsLoading(false);
    };
  }, []);

  const sendMessage = useCallback(
    (message: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
        setTimeout(() => sendMessage(message), 500);
        return;
      }

      setMessages((prev) => [...prev, { role: 'user', content: message }]);
      setIsLoading(true);
      wsRef.current.send(
        JSON.stringify({ action: 'message', message, product_id: productIdRef.current }),
      );
    },
    [connect],
  );

  const clearHistory = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'clear' }));
    }
    setMessages([]);
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { messages, isLoading, mcpState, sendMessage, clearHistory, connect, disconnect };
}

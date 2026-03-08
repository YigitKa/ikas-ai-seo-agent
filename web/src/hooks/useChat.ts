import { useCallback, useRef, useState } from 'react';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export function useChat(productId?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'response') {
        setMessages((prev) => [...prev, { role: 'assistant', content: data.message }]);
        setIsLoading(false);
      } else if (data.type === 'error') {
        setMessages((prev) => [...prev, { role: 'system', content: `Error: ${data.message}` }]);
        setIsLoading(false);
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
        // retry after connection
        setTimeout(() => sendMessage(message), 500);
        return;
      }

      setMessages((prev) => [...prev, { role: 'user', content: message }]);
      setIsLoading(true);
      wsRef.current.send(JSON.stringify({ message, product_id: productId }));
    },
    [connect, productId],
  );

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { messages, isLoading, sendMessage, connect, disconnect };
}

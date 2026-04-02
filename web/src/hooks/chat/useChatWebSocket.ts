import { useCallback, useEffect, useRef, useState } from 'react';
import type { ActiveSkillSummary, ChatWsMessage, SeoSuggestion } from '../../types';
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
  setActiveSkill: React.Dispatch<React.SetStateAction<ActiveSkillSummary | null>>;
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
  // Keep all deps in a ref so that WS event handlers always invoke the latest
  // versions without requiring connect() to change identity.
  const latestRef = useRef(deps);
  latestRef.current = deps;

  const [isReconnecting, setIsReconnecting] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const clearReasonRef = useRef<'switch' | 'clear'>('clear');
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalDisconnectRef = useRef(false);
  const lastSentPayloadRef = useRef<{ message: string; productId?: string; hidden: boolean } | null>(null);
  const preferredSkillSlugRef = useRef<string | null>(null);

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
  // WebSocket connect — stable identity (reads callbacks from latestRef)
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

      const productId = latestRef.current.productContextRef.current?.id;
      if (productId) {
        ws.send(JSON.stringify({ action: 'set_context', product_id: productId }));
      }
      if (preferredSkillSlugRef.current) {
        ws.send(JSON.stringify({ action: 'set_skill', skill_slug: preferredSkillSlugRef.current }));
      }
    };

    ws.onmessage = (event) => {
      const h = latestRef.current;
      const data: ChatWsMessage = JSON.parse(event.data);
      if (data.type === 'chunk' || data.type === 'thinking_chunk') {
        h.incrementChunkCount();
      }

      switch (data.type) {
        case 'chunk':
          h.appendAssistantChunk(data.content || '');
          break;

        case 'thinking_chunk':
          h.appendThinkingChunk(data.content || '');
          break;

        case 'response':
        case 'response_done': {
          h.clearActiveAutoIntro();
          h.finalizeAssistantMessage(data);
          if ((data as unknown as Record<string, unknown>).product_updated && h.onProductUpdated) {
            h.onProductUpdated();
          }
          break;
        }

        case 'error':
          h.finishPendingRequest();
          h.clearActiveAutoIntro();
          h.setMessages((prev) => [
            ...prev,
            { role: 'system', content: data.content || data.message || 'Hata' },
          ]);
          break;

        case 'cancelled':
          h.finishPendingRequest();
          h.clearActiveAutoIntro();
          h.setMessages((prev) => [
            ...prev,
            { role: 'system', content: data.message || 'Istek durduruldu.' },
          ]);
          break;

        case 'thinking':
          break;

        case 'mcp_status':
          h.setMcpState({
            hasToken: data.has_token ?? false,
            initialized: data.initialized ?? false,
            toolCount: data.tool_count ?? 0,
            tools: data.tools ?? [],
            message: data.message || '',
          });
          break;

        case 'skill_status':
          h.setActiveSkill(data.active_skill ?? null);
          if (data.active_skill?.slug) {
            preferredSkillSlugRef.current = data.active_skill.slug;
          } else {
            preferredSkillSlugRef.current = null;
          }
          break;

        case 'context_set':
          h.setPendingSuggestion(data.pending_suggestion ?? null);
          if (data.product_id) {
            h.sendHiddenAutoIntro(data.product_id);
          }
          break;

        case 'cleared':
          h.finishPendingRequest();
          h.clearActiveAutoIntro();
          // On product-switch clears the history is restored from localStorage
          // by useChat's switch effect, so we must not wipe it here.
          if (clearReasonRef.current !== 'switch') {
            h.resetToContextIntro();
          }
          clearReasonRef.current = 'clear';
          break;
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      latestRef.current.finishPendingRequest();
      latestRef.current.clearAutoIntro();

      if (!intentionalDisconnectRef.current) {
        scheduleReconnect();
      }
    };
  }, [scheduleReconnect]);

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
      const productId = latestRef.current.productContextRef.current?.id;

      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
        window.setTimeout(() => sendMessage(message, options), 500);
        return;
      }

      if (!options?.hidden) {
        latestRef.current.setMessages((prev) => [...prev, { role: 'user', content: message }]);
      }
      lastSentPayloadRef.current = { message, productId, hidden: !!options?.hidden };
      latestRef.current.startPendingRequest();
      const payload: Record<string, unknown> = { action: 'message', message };
      if (productId) {
        payload.product_id = productId;
      }
      wsRef.current.send(JSON.stringify(payload));
    },
    [connect],
  );

  const retryLastMessage = useCallback(() => {
    const payload = lastSentPayloadRef.current;
    if (!payload) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    // Remove the failed assistant message (last message if it's from assistant)
    latestRef.current.setMessages((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].role === 'assistant') {
        return prev.slice(0, -1);
      }
      return prev;
    });

    latestRef.current.startPendingRequest();
    const nextPayload: Record<string, unknown> = { action: 'message', message: payload.message };
    if (payload.productId) {
      nextPayload.product_id = payload.productId;
    }
    wsRef.current.send(JSON.stringify(nextPayload));
  }, []);

  const clearHistory = useCallback(() => {
    latestRef.current.clearAutoIntro();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      clearReasonRef.current = 'clear';
      wsRef.current.send(JSON.stringify({ action: 'clear' }));
      return;
    }
    latestRef.current.resetToContextIntro();
  }, []);

  const cancelMessage = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN || latestRef.current.pendingSinceRef.current === null) {
      return;
    }
    wsRef.current.send(JSON.stringify({ action: 'cancel' }));
  }, []);

  const syncPreferredSkillSlug = useCallback((skillSlug: string | null) => {
    preferredSkillSlugRef.current = skillSlug?.trim() ? skillSlug.trim() : null;
  }, []);

  const setSelectedSkill = useCallback(
    (skillSlug: string) => {
      const normalized = skillSlug.trim();
      preferredSkillSlugRef.current = normalized || null;

      if (!normalized) {
        latestRef.current.setActiveSkill(null);
      }

      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connect();
        window.setTimeout(() => {
          if (normalized) {
            setSelectedSkill(normalized);
          }
        }, 500);
        return;
      }

      wsRef.current.send(JSON.stringify({ action: 'set_skill', skill_slug: normalized }));
    },
    [connect],
  );

  const clearSelectedSkill = useCallback(() => {
    preferredSkillSlugRef.current = null;
    latestRef.current.setActiveSkill(null);

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connect();
      window.setTimeout(() => clearSelectedSkill(), 500);
      return;
    }

    wsRef.current.send(JSON.stringify({ action: 'clear_skill' }));
  }, [connect]);

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
    setSelectedSkill,
    clearSelectedSkill,
    syncPreferredSkillSlug,
  };
}

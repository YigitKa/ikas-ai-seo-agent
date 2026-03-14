import { useCallback, useRef, useState } from 'react';
import type { MCPToolInfo, SeoSuggestion } from '../../types';

export interface MCPState {
  hasToken: boolean;
  initialized: boolean;
  toolCount: number;
  tools: MCPToolInfo[];
  message: string;
}

export function useChatStatus() {
  const [isLoading, setIsLoading] = useState(false);
  const [pendingSince, setPendingSince] = useState<number | null>(null);
  const [liveChunkCount, setLiveChunkCount] = useState(0);
  const [liveTokenEstimate, setLiveTokenEstimate] = useState(0);
  const [mcpState, setMcpState] = useState<MCPState>({
    hasToken: false,
    initialized: false,
    toolCount: 0,
    tools: [],
    message: '',
  });
  const [pendingSuggestion, setPendingSuggestion] = useState<SeoSuggestion | null>(null);

  const pendingSinceRef = useRef<number | null>(null);

  const startPendingRequest = useCallback(() => {
    const startedAt = performance.now();
    pendingSinceRef.current = startedAt;
    setPendingSince(startedAt);
    setLiveChunkCount(0);
    setLiveTokenEstimate(0);
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

  const incrementChunkCount = useCallback(() => {
    setLiveChunkCount((prev) => prev + 1);
  }, []);

  const addTokenEstimate = useCallback((tokens: number) => {
    setLiveTokenEstimate((prev) => prev + tokens);
  }, []);

  return {
    // State values
    isLoading,
    pendingSince,
    liveChunkCount,
    liveTokenEstimate,
    mcpState,
    pendingSuggestion,
    pendingSinceRef,

    // Setters
    setMcpState,
    setPendingSuggestion,

    // Actions
    startPendingRequest,
    finishPendingRequest,
    incrementChunkCount,
    addTokenEstimate,
  };
}

import { useCallback, useRef, useState } from 'react';

const AUTO_PRODUCT_OVERVIEW_PROMPT =
  'Bu urunun SEO durumunu incele ve ilk tespitlerini bir asistan gibi proaktif bir dille bana sun.';

interface UseChatAutoIntroDeps {
  productContextRef: React.RefObject<{ id?: string } | undefined>;
  wsRef: React.RefObject<WebSocket | null>;
  startPendingRequest: () => void;
}

export function useChatAutoIntro(deps: UseChatAutoIntroDeps) {
  const { productContextRef, wsRef, startPendingRequest } = deps;

  const [autoIntroProductId, setAutoIntroProductId] = useState<string | null>(null);
  const queuedAutoIntroProductIdRef = useRef<string | null>(null);
  const activeAutoIntroProductIdRef = useRef<string | null>(null);

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
  }, [startPendingRequest, syncAutoIntroState, wsRef, productContextRef]);

  return {
    autoIntroProductId,
    queueAutoIntro,
    clearAutoIntro,
    clearActiveAutoIntro,
    sendHiddenAutoIntro,
  };
}

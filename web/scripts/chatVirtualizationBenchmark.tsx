import { performance } from 'node:perf_hooks';
import React from 'react';
import { JSDOM } from 'jsdom';
import { createRoot } from 'react-dom/client';
import { VirtuosoMockContext } from 'react-virtuoso';
import {
  createChatMessage,
  type ChatMessage,
} from '../src/hooks/chat/chatMessageModel';

const VIEWPORT_HEIGHT = 720;
const ITEM_HEIGHT = 164;
const MESSAGE_COUNT = 2000;

function installDom(): JSDOM {
  const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
    pretendToBeVisual: true,
    url: 'http://localhost/',
  });

  const { window } = dom;
  const resizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };

  Object.defineProperty(globalThis, 'window', { value: window, configurable: true });
  Object.defineProperty(globalThis, 'document', { value: window.document, configurable: true });
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
  Object.defineProperty(globalThis, 'React', { value: React, configurable: true });
  Object.defineProperty(globalThis, 'HTMLElement', { value: window.HTMLElement, configurable: true });
  Object.defineProperty(globalThis, 'Element', { value: window.Element, configurable: true });
  Object.defineProperty(globalThis, 'Node', { value: window.Node, configurable: true });
  Object.defineProperty(globalThis, 'DocumentFragment', { value: window.DocumentFragment, configurable: true });
  Object.defineProperty(globalThis, 'MutationObserver', { value: window.MutationObserver, configurable: true });
  Object.defineProperty(globalThis, 'getComputedStyle', {
    value: window.getComputedStyle.bind(window),
    configurable: true,
  });

  window.requestAnimationFrame = ((callback: FrameRequestCallback) => window.setTimeout(
    () => callback(performance.now()),
    16,
  )) as typeof window.requestAnimationFrame;
  window.cancelAnimationFrame = ((handle: number) => window.clearTimeout(handle)) as typeof window.cancelAnimationFrame;
  window.scrollTo = () => undefined;
  window.ResizeObserver = resizeObserver as typeof window.ResizeObserver;

  Object.defineProperty(globalThis, 'requestAnimationFrame', {
    value: window.requestAnimationFrame.bind(window),
    configurable: true,
  });
  Object.defineProperty(globalThis, 'cancelAnimationFrame', {
    value: window.cancelAnimationFrame.bind(window),
    configurable: true,
  });
  Object.defineProperty(globalThis, 'ResizeObserver', {
    value: resizeObserver,
    configurable: true,
  });

  return dom;
}

function waitForFrames(frameCount = 6): Promise<void> {
  return new Promise((resolve) => {
    let remaining = frameCount;

    const tick = () => {
      if (remaining <= 0) {
        resolve();
        return;
      }

      remaining -= 1;
      window.requestAnimationFrame(tick);
    };

    tick();
  });
}

function buildMessages(count: number): ChatMessage[] {
  return Array.from({ length: count }, (_, index) => {
    const isAssistant = index % 2 === 1;

    return createChatMessage({
      role: isAssistant ? 'assistant' : 'user',
      content: isAssistant
        ? `## SEO ozet ${index}\n\n- Meta title varyasyonu ${index}\n- Meta description iyilestirmesi ${index}\n- Kategori baglami ve keyword dagilimi ${index}`
        : `Urun icin ${index}. tur revizyonu yap ve aciklamayi kategoriye gore optimize et.`,
      thinking: isAssistant && index % 6 === 1
        ? `Analiz adimi ${index}: mevcut title, description ve keyword tutarliligi kontrol edildi.`
        : undefined,
      toolResults: isAssistant && index % 10 === 1
        ? [
          {
            tool: 'get_product_details',
            arguments: { product_id: `product-${index}` },
            result: JSON.stringify({
              product_id: `product-${index}`,
              title: `Benchmark urunu ${index}`,
              summary: `Uzun arac payload'i ${index}`.repeat(12),
            }),
          },
        ]
        : undefined,
      meta: isAssistant
        ? {
          model: 'benchmark-model',
          total_tokens: 280 + index,
          elapsed_seconds: 1.8,
        }
        : undefined,
    });
  });
}

function renderList(
  ChatMessages: typeof import('../src/components/chat/ChatMessages').ChatMessages,
  messages: ChatMessage[],
  options?: { isLoading?: boolean },
) {
  return (
    <VirtuosoMockContext.Provider value={{ viewportHeight: VIEWPORT_HEIGHT, itemHeight: ITEM_HEIGHT }}>
      <div style={{ height: `${VIEWPORT_HEIGHT}px`, width: '960px' }}>
        <ChatMessages
          showStarterState={false}
          isLoading={options?.isLoading ?? false}
          isInspectingProduct={false}
          isAutoIntroActive={false}
          messages={messages}
          assistantLabel="Benchmark Assistant"
          liveContextLength={32768}
          liveElapsedSeconds={2.4}
          onStarterPrompt={() => undefined}
          onApplyOption={() => undefined}
          onRetry={() => undefined}
        />
      </div>
    </VirtuosoMockContext.Provider>
  );
}

async function measureRender(run: () => void): Promise<number> {
  const startedAt = performance.now();
  run();
  await waitForFrames();
  return Number((performance.now() - startedAt).toFixed(2));
}

async function main() {
  const dom = installDom();
  const mountNode = dom.window.document.getElementById('root');
  const { ChatMessages } = await import('../src/components/chat/ChatMessages');

  if (!mountNode) {
    throw new Error('Benchmark root bulunamadi.');
  }

  const root = createRoot(mountNode);
  const baseMessages = buildMessages(MESSAGE_COUNT);

  const initialMountMs = await measureRender(() => {
    root.render(renderList(ChatMessages, baseMessages));
  });

  const renderedRows = mountNode.querySelectorAll('[data-index]').length;
  const renderedDomNodes = mountNode.querySelectorAll('*').length;

  const appendedMessages = [
    ...baseMessages,
    createChatMessage({
      role: 'assistant',
      content: 'Canli benchmark cevabi: son mesaja ek performans olcumu uygulandi.',
      thinking: 'Streaming append benchmark adimi.',
    }),
  ];

  const appendMs = await measureRender(() => {
    root.render(renderList(ChatMessages, appendedMessages, { isLoading: true }));
  });

  const streamedMessages = appendedMessages.map((message, index) => {
    if (index !== appendedMessages.length - 1) {
      return message;
    }

    return {
      ...message,
      content: `${message.content}\n\n- Ek streaming parcasi A\n- Ek streaming parcasi B\n- Ek streaming parcasi C`,
      thinking: `${message.thinking ?? ''} Son parcada ek context olculdu.`,
    };
  });

  const streamUpdateMs = await measureRender(() => {
    root.render(renderList(ChatMessages, streamedMessages, { isLoading: true }));
  });

  const renderedRowsAfterStream = mountNode.querySelectorAll('[data-index]').length;

  const metrics = {
    message_count: MESSAGE_COUNT,
    rendered_rows: renderedRows,
    rendered_rows_after_stream: renderedRowsAfterStream,
    virtualization_ratio_pct: Number(((renderedRows / MESSAGE_COUNT) * 100).toFixed(2)),
    dom_node_count: renderedDomNodes,
    initial_mount_ms: initialMountMs,
    append_ms: appendMs,
    stream_update_ms: streamUpdateMs,
  };

  console.table(metrics);

  if (renderedRows >= 120) {
    throw new Error(`Virtualization beklenenden fazla satir render ediyor: ${renderedRows}`);
  }

  root.unmount();
  dom.window.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

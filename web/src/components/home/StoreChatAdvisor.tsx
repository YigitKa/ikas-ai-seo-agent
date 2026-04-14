import { lazy, Suspense, useCallback, useRef, useState } from 'react';
import { STORE_CHAT_CATEGORIES } from './storeChatConstants';
import type { StoreChatCategory } from './storeChatConstants';

const ChatPanel = lazy(() => import('../ChatPanel'));

/** Flat list of all store prompts for the ChatPanel starter state. */
const ALL_STORE_PROMPTS = STORE_CHAT_CATEGORIES.flatMap((category) => category.prompts);

interface PendingStorePrompt {
  id: string;
  text: string;
}

interface StoreChatAdvisorProps {
  storeName?: string;
  isOpen: boolean;
  onClose: () => void;
}

function CategoryCard({
  category,
  isExpanded,
  onToggle,
  onPromptClick,
}: {
  category: StoreChatCategory;
  isExpanded: boolean;
  onToggle: () => void;
  onPromptClick: (template: string) => void;
}) {
  return (
    <div
      className="rounded-xl transition-all"
      style={{
        background: isExpanded
          ? 'var(--tint-primary-bg)'
          : 'var(--color-divider)',
        border: isExpanded
          ? '1px solid var(--tint-primary-soft)'
          : '1px solid var(--color-divider)',
      }}
    >
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left transition-colors hover:bg-white/[0.03]"
        style={{ borderRadius: 'inherit' }}
      >
        <span className="text-[18px] leading-none">{category.icon}</span>
        <span
          className="flex-1 text-[12px] font-semibold"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {category.label}
        </span>
        <svg
          className="h-3.5 w-3.5 transition-transform"
          style={{
            color: 'var(--color-text-muted)',
            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)',
          }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="space-y-0.5 px-2 pb-2">
          {category.prompts.map((prompt) => (
            <button
              key={prompt.label}
              onClick={() => onPromptClick(prompt.template)}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[11px] transition-colors hover:bg-white/[0.06]"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              <svg
                className="h-3 w-3 flex-shrink-0"
                style={{ color: 'var(--color-text-muted)' }}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {prompt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function StoreChatAdvisor({ storeName, isOpen, onClose }: StoreChatAdvisorProps) {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [chatStarted, setChatStarted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<PendingStorePrompt | null>(null);
  const nextPromptIdRef = useRef(0);

  const handlePromptClick = useCallback((template: string) => {
    const promptId = `store-prompt-${nextPromptIdRef.current}`;
    nextPromptIdRef.current += 1;
    setPendingPrompt({ id: promptId, text: template });
    setChatStarted(true);
  }, []);

  const handleBackToCategories = useCallback(() => {
    setPendingPrompt(null);
    setExpandedCategory(null);
    setChatStarted(false);
  }, []);

  const handlePendingPromptConsumed = useCallback((promptId: string) => {
    setPendingPrompt((current) => (current?.id === promptId ? null : current));
  }, []);

  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen((current) => !current);
  }, []);

  const handleClose = useCallback(() => {
    onClose();
    window.setTimeout(() => {
      setChatStarted(false);
      setExpandedCategory(null);
      setIsFullscreen(false);
      setPendingPrompt(null);
    }, 350);
  }, [onClose]);

  return (
    <>
      <div
        className="fixed inset-0 z-40 transition-opacity duration-300"
        style={{
          background: 'var(--color-overlay)',
          opacity: isOpen ? 1 : 0,
          pointerEvents: isOpen ? 'auto' : 'none',
        }}
        onClick={handleClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-hidden={!isOpen}
        aria-labelledby="store-chat-advisor-title"
        data-testid="store-chat-advisor-panel"
        className="fixed z-50 flex flex-col"
        style={{
          top: 0,
          right: 0,
          bottom: 0,
          left: isFullscreen ? 0 : 'auto',
          width: isFullscreen ? '100vw' : 'min(640px, 95vw)',
          maxWidth: '100vw',
          height: '100vh',
          background: 'var(--chat-shell-bg)',
          borderLeft: isFullscreen ? 'none' : '1px solid var(--chat-shell-border)',
          boxShadow: isFullscreen ? '0 0 0 rgba(0,0,0,0)' : '-12px 0 48px var(--color-overlay-dark)',
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.32s cubic-bezier(0.4,0,0.2,1), width 0.22s ease, left 0.22s ease',
        }}
      >
        <div
          className="flex flex-shrink-0 items-center gap-3 px-4 py-3.5"
          style={{ borderBottom: '1px solid var(--chat-section-border)' }}
        >
          <div
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl"
            style={{ background: 'var(--tint-primary-soft)', color: 'var(--color-primary-light)' }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          </div>

          <div className="min-w-0 flex-1">
            <div
              id="store-chat-advisor-title"
              className="text-[13px] font-semibold"
              style={{ color: 'var(--color-text-primary)' }}
            >
              AI Magaza Asistani
            </div>
            <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
              {storeName ? `${storeName} - Siparisler, stok, musteriler ve daha fazlasi` : 'Magazanizi dogal dilde yonetin'}
            </div>
          </div>

          {chatStarted && (
            <button
              onClick={handleBackToCategories}
              aria-label="Kategorilere don"
              className="flex h-8 items-center gap-1.5 rounded-xl px-2.5 transition-all hover:bg-white/[0.06]"
              style={{ color: 'var(--color-text-muted)', fontSize: '11px' }}
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              Kategoriler
            </button>
          )}

          <button
            onClick={handleToggleFullscreen}
            aria-label={isFullscreen ? 'Tam ekrandan cik' : 'Tam ekran yap'}
            aria-pressed={isFullscreen}
            className="flex h-8 items-center gap-1.5 rounded-xl px-2.5 transition-all hover:bg-white/[0.06]"
            style={{ color: 'var(--color-text-muted)', fontSize: '11px' }}
            title={isFullscreen ? 'Standart gorunume don' : 'Tam ekran gorunume gec'}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {isFullscreen ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 9H5V5m10 0h4v4m0 6v4h-4m-6 0H5v-4"
                />
              ) : (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8 3H5a2 2 0 00-2 2v3m16 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M8 21H5a2 2 0 01-2-2v-3"
                />
              )}
            </svg>
            <span>{isFullscreen ? 'Daralt' : 'Tam ekran'}</span>
          </button>

          <button
            onClick={handleClose}
            aria-label="Kapat"
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl transition-all hover:bg-white/[0.06]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="relative min-h-0 flex-1 overflow-hidden">
          {!chatStarted ? (
            <div className="h-full overflow-y-auto p-4">
              <div className="mb-4">
                <p
                  className="text-[12px] leading-relaxed"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  Magazanizi AI ile yonetin. Bir kategori secin veya dogrudan sohbete baslayin.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {STORE_CHAT_CATEGORIES.map((category) => (
                  <CategoryCard
                    key={category.id}
                    category={category}
                    isExpanded={expandedCategory === category.id}
                    onToggle={() =>
                      setExpandedCategory((current) => (current === category.id ? null : category.id))
                    }
                    onPromptClick={handlePromptClick}
                  />
                ))}
              </div>

              <button
                onClick={() => setChatStarted(true)}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-[12px] font-medium transition-all hover:brightness-110"
                style={{
                  background: 'var(--chat-bubble-user-bg)',
                  border: '1px solid var(--chat-bubble-user-border)',
                  color: 'var(--color-text-brand-soft)',
                }}
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
                Serbest sohbete basla
              </button>
            </div>
          ) : (
            <Suspense
              fallback={
                <div
                  className="flex h-full items-center justify-center text-[12px]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Yukleniyor...
                </div>
              }
            >
              {isOpen && (
                <ChatPanel
                  chatScope="store"
                  starterPrompts={ALL_STORE_PROMPTS}
                  pendingMessage={pendingPrompt}
                  onPendingMessageConsumed={handlePendingPromptConsumed}
                />
              )}
            </Suspense>
          )}
        </div>
      </div>
    </>
  );
}

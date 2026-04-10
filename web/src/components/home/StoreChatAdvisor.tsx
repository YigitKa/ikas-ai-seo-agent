import { lazy, Suspense, useCallback, useRef, useState } from 'react';
import { STORE_CHAT_CATEGORIES } from './storeChatConstants';
import type { StoreChatCategory } from './storeChatConstants';

const ChatPanel = lazy(() => import('../ChatPanel'));

/** Flat list of all store prompts for the ChatPanel starter state. */
const ALL_STORE_PROMPTS = STORE_CHAT_CATEGORIES.flatMap((c) => c.prompts);

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
          ? 'rgba(99,102,241,0.08)'
          : 'rgba(148,163,184,0.06)',
        border: isExpanded
          ? '1px solid rgba(99,102,241,0.2)'
          : '1px solid rgba(148,163,184,0.12)',
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

  /** Ref to the sendMessage function exposed by ChatPanel's useChat.
   *  We obtain it indirectly: when the user clicks a category prompt
   *  BEFORE the chat is mounted, we queue it and send once mounted. */
  const queuedPromptRef = useRef<string | null>(null);
  const sendRef = useRef<((msg: string) => void) | null>(null);

  const handlePromptClick = useCallback((template: string) => {
    if (sendRef.current) {
      // Chat already mounted — send directly
      sendRef.current(template);
    } else {
      // Queue for when ChatPanel mounts
      queuedPromptRef.current = template;
    }
    setChatStarted(true);
  }, []);

  const handleClose = () => {
    onClose();
    // Reset state after slide-out animation completes
    setTimeout(() => {
      setChatStarted(false);
      setExpandedCategory(null);
      queuedPromptRef.current = null;
      sendRef.current = null;
    }, 350);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 transition-opacity duration-300"
        style={{
          background: 'rgba(0,0,0,0.55)',
          opacity: isOpen ? 1 : 0,
          pointerEvents: isOpen ? 'auto' : 'none',
        }}
        onClick={handleClose}
      />

      {/* Slide-in panel */}
      <div
        className="fixed inset-y-0 right-0 z-50 flex flex-col"
        style={{
          width: 'min(640px, 95vw)',
          background: 'linear-gradient(160deg, rgba(8,14,32,0.99), rgba(12,20,40,0.98))',
          borderLeft: '1px solid rgba(148,163,184,0.14)',
          boxShadow: '-12px 0 48px rgba(0,0,0,0.5)',
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.32s cubic-bezier(0.4,0,0.2,1)',
        }}
      >
        {/* Panel header */}
        <div
          className="flex flex-shrink-0 items-center gap-3 px-4 py-3.5"
          style={{ borderBottom: '1px solid rgba(148,163,184,0.1)' }}
        >
          <div
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl"
            style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}
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
            <div className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              AI Magaza Asistani
            </div>
            <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
              {storeName ? `${storeName} - Siparisler, stok, musteriler ve daha fazlasi` : 'Magazanizi dogal dilde yonetin'}
            </div>
          </div>

          {chatStarted && (
            <button
              onClick={() => setChatStarted(false)}
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

        {/* Content area */}
        <div className="relative min-h-0 flex-1 overflow-hidden">
          {!chatStarted ? (
            /* Category cards grid */
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
                {STORE_CHAT_CATEGORIES.map((cat) => (
                  <CategoryCard
                    key={cat.id}
                    category={cat}
                    isExpanded={expandedCategory === cat.id}
                    onToggle={() =>
                      setExpandedCategory((prev) => (prev === cat.id ? null : cat.id))
                    }
                    onPromptClick={handlePromptClick}
                  />
                ))}
              </div>

              {/* Direct chat button */}
              <button
                onClick={() => setChatStarted(true)}
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-[12px] font-medium transition-all hover:brightness-110"
                style={{
                  background: 'linear-gradient(135deg, rgba(99,102,241,0.18), rgba(139,92,246,0.14))',
                  border: '1px solid rgba(99,102,241,0.25)',
                  color: '#c7d2fe',
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
            /* Chat panel in store-wide scope */
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
                />
              )}
            </Suspense>
          )}
        </div>
      </div>
    </>
  );
}

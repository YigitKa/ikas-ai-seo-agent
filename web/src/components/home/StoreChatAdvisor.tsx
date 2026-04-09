import { lazy, Suspense } from 'react';

const ChatPanel = lazy(() => import('../ChatPanel'));

const STORE_STARTER_PROMPTS = [
  { label: 'Genel SEO durumumu ozetle', template: 'Magazamin genel SEO durumunu ozetle.' },
  { label: 'Oncelikli iyilestirmeler', template: 'En acil iyilestirmem gereken alanlar neler?' },
  { label: 'Kategori oncelikleri', template: 'Hangi urun kategorilerine oncelik vermeliyim?' },
  { label: 'Toplu optimizasyon plani', template: 'Toplu optimizasyon icin bir plan olustur.' },
];

interface StoreChatAdvisorProps {
  storeName?: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function StoreChatAdvisor({ storeName, isOpen, onClose }: StoreChatAdvisorProps) {
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
        onClick={onClose}
      />

      {/* Slide-in panel */}
      <div
        className="fixed inset-y-0 right-0 z-50 flex flex-col"
        style={{
          width: 'min(480px, 95vw)',
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
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </div>

          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              AI SEO Danismani
            </div>
            <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
              {storeName ? `${storeName} icin` : 'Magazaniz icin'}
            </div>
          </div>

          <button
            onClick={onClose}
            aria-label="Kapat"
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl transition-all hover:bg-white/[0.06]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Chat area */}
        <div className="relative min-h-0 flex-1 overflow-hidden">
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
            {isOpen && <ChatPanel starterPrompts={STORE_STARTER_PROMPTS} />}
          </Suspense>
        </div>
      </div>
    </>
  );
}

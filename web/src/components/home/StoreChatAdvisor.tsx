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
}

export default function StoreChatAdvisor({ storeName }: StoreChatAdvisorProps) {
  return (
    <div
      className="enterprise-surface flex flex-col rounded-2xl"
      style={{
        background: 'linear-gradient(160deg, rgba(15,23,42,0.88), rgba(30,41,59,0.62))',
        border: '1px solid rgba(148,163,184,0.14)',
        height: 480,
        minHeight: 400,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2.5 rounded-t-2xl px-4 py-3"
        style={{ borderBottom: '1px solid rgba(148,163,184,0.1)' }}
      >
        <div
          className="flex h-8 w-8 items-center justify-center rounded-xl"
          style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc' }}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </div>
        <div>
          <div className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            AI SEO Danismani
          </div>
          <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
            {storeName ? `${storeName} icin` : 'Magazaniz icin'}
          </div>
        </div>
      </div>

      {/* Chat */}
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center" style={{ color: 'var(--color-text-muted)' }}>
              Yukleniyor...
            </div>
          }
        >
          <ChatPanel starterPrompts={STORE_STARTER_PROMPTS} />
        </Suspense>
      </div>
    </div>
  );
}

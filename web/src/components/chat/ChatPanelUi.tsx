import type { StarterPrompt } from './promptParams';

export function ChatStatusPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'neutral' | 'success' | 'warn';
}) {
  const palette = {
    neutral: {
      background: 'rgba(148, 163, 184, 0.08)',
      color: 'var(--color-text-secondary)',
      border: '1px solid rgba(148, 163, 184, 0.12)',
    },
    success: {
      background: 'rgba(16, 185, 129, 0.10)',
      color: '#34d399',
      border: '1px solid rgba(16, 185, 129, 0.16)',
    },
    warn: {
      background: 'rgba(245, 158, 11, 0.10)',
      color: '#fbbf24',
      border: '1px solid rgba(245, 158, 11, 0.16)',
    },
  } as const;

  return (
    <div
      className="rounded-full px-2.5 py-1 text-[10px] font-medium backdrop-blur-sm"
      style={palette[tone]}
      title={`${label}: ${value}`}
    >
      {label}: {value}
    </div>
  );
}

export function ReconnectingBanner() {
  return (
    <div
      className="mx-3 mt-3 flex items-center gap-2 rounded-xl px-4 py-2 text-[12px] font-medium"
      style={{
        background: 'rgba(245, 158, 11, 0.08)',
        border: '1px solid rgba(245, 158, 11, 0.24)',
        color: '#fbbf24',
      }}
    >
      <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
        />
      </svg>
      Yeniden bağlanılıyor...
    </div>
  );
}

export function StarterStateCard({
  prompts,
  onPromptClick,
  disabled,
}: {
  prompts: StarterPrompt[];
  onPromptClick: (prompt: StarterPrompt) => void;
  disabled: boolean;
}) {
  return (
    <div
      className="rounded-2xl p-4 text-center shadow-lg"
      style={{
        background: 'linear-gradient(160deg, rgba(99, 102, 241, 0.14), rgba(17, 24, 39, 0.22))',
        border: '1px solid rgba(99, 102, 241, 0.22)',
        boxShadow: '0 14px 30px rgba(14, 21, 48, 0.28)',
      }}
    >
      <div
        className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl"
        style={{
          background: 'rgba(99, 102, 241, 0.12)',
          color: '#c7d2fe',
        }}
      >
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </div>
      <p className="mt-3 text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
        Secili urunun mevcut SEO metrikleri ve eldeki alanlariyla sohbet hazir.
      </p>
      <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Mesaj yaz veya {'{'} ile `productDescription` veya `seoMetricsSummary` gibi alanlari mesaja ekleyebilirsin.
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {prompts.map((prompt) => (
          <button
            key={prompt.label}
            onClick={() => onPromptClick(prompt)}
            disabled={disabled}
            className="rounded-full px-3 py-1.5 text-[11px] font-medium transition-all hover:opacity-90 disabled:opacity-40"
            style={{
              background: 'rgba(99, 102, 241, 0.12)',
              color: '#c7d2fe',
              border: '1px solid rgba(99, 102, 241, 0.2)',
            }}
          >
            {prompt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

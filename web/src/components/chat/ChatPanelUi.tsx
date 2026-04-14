import type { StarterPrompt } from './promptParams';

export interface ChatStatusItem {
  label: string;
  value: string;
  tone: 'neutral' | 'success' | 'warn';
}

export function ChatStatusDeck({ items }: { items: ChatStatusItem[] }) {
  const palette = {
    neutral: {
      surface: 'var(--chat-muted-card-bg)',
      border: '1px solid var(--chat-section-border)',
      labelColor: 'var(--color-text-secondary)',
      valueColor: 'var(--color-text-primary)',
      glow: 'var(--alpha-white-3)',
      dot: 'var(--color-text-secondary)',
    },
    success: {
      surface: 'var(--tint-success-bg)',
      border: '1px solid var(--color-border-success)',
      labelColor: 'var(--color-text-success)',
      valueColor: 'var(--color-text-success-soft)',
      glow: 'var(--tint-success-soft)',
      dot: 'var(--color-icon-success)',
    },
    warn: {
      surface: 'var(--tint-warning-bg)',
      border: '1px solid var(--color-border-warning)',
      labelColor: 'var(--color-text-warning)',
      valueColor: 'var(--color-text-warning-soft)',
      glow: 'var(--tint-warning-soft)',
      dot: 'var(--color-icon-warning)',
    },
  } as const;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {items.map((item) => {
        const styles = palette[item.tone];
        return (
          <div
            key={`${item.label}-${item.value}`}
            className="inline-flex min-w-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium backdrop-blur-sm"
            style={{
              background: styles.surface,
              border: styles.border,
              boxShadow: `0 6px 16px ${styles.glow}`,
            }}
            title={`${item.label}: ${item.value}`}
          >
            <span
              className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
              style={{ background: styles.dot }}
            />
            <span
              className="uppercase tracking-[0.12em]"
              style={{ color: styles.labelColor }}
            >
              {item.label}
            </span>
            <span className="truncate" style={{ color: styles.valueColor }}>
              {item.value}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function ReconnectingBanner() {
  return (
    <div
      className="mx-3 mt-3 flex items-center gap-2 rounded-xl px-4 py-2 text-[12px] font-medium"
      style={{
        background: 'var(--tint-warning-bg)',
        border: '1px solid var(--color-border-warning)',
        color: 'var(--color-icon-warning)',
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
        background: 'var(--chat-starter-bg)',
        border: '1px solid var(--chat-starter-border)',
        boxShadow: 'var(--chat-starter-shadow)',
      }}
    >
      <div
        className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl"
        style={{
          background: 'var(--chat-starter-chip-bg)',
          border: '1px solid var(--chat-starter-chip-border)',
          color: 'var(--color-text-brand-soft)',
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
              background: 'var(--chat-starter-chip-bg)',
              color: 'var(--color-text-brand-soft)',
              border: '1px solid var(--chat-starter-chip-border)',
            }}
          >
            {prompt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

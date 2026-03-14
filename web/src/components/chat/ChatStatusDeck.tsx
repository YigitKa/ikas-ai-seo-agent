// Extracted from ChatPanelUi.tsx for independent import

export interface ChatStatusItem {
  label: string;
  value: string;
  tone: 'neutral' | 'success' | 'warn';
}

const palette = {
  neutral: {
    surface: 'rgba(148, 163, 184, 0.08)',
    border: '1px solid rgba(148, 163, 184, 0.14)',
    labelColor: 'var(--color-text-secondary)',
    valueColor: 'var(--color-text-primary)',
    glow: 'rgba(148, 163, 184, 0.08)',
    dot: '#94a3b8',
  },
  success: {
    surface: 'rgba(16, 185, 129, 0.12)',
    border: '1px solid rgba(16, 185, 129, 0.18)',
    labelColor: 'rgba(167, 243, 208, 0.82)',
    valueColor: '#d1fae5',
    glow: 'rgba(16, 185, 129, 0.1)',
    dot: '#34d399',
  },
  warn: {
    surface: 'rgba(245, 158, 11, 0.12)',
    border: '1px solid rgba(245, 158, 11, 0.18)',
    labelColor: 'rgba(253, 230, 138, 0.86)',
    valueColor: '#fef3c7',
    glow: 'rgba(245, 158, 11, 0.1)',
    dot: '#fbbf24',
  },
} as const;

export function ChatStatusDeck({ items }: { items: ChatStatusItem[] }) {
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

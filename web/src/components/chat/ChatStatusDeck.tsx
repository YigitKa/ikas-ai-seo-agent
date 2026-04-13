// Extracted from ChatPanelUi.tsx for independent import

export interface ChatStatusItem {
  label: string;
  value: string;
  tone: 'neutral' | 'success' | 'warn';
}

const palette = {
  neutral: {
    surface: 'var(--color-divider)',
    border: '1px solid var(--color-divider)',
    labelColor: 'var(--color-text-secondary)',
    valueColor: 'var(--color-text-primary)',
    glow: 'var(--color-divider)',
    dot: 'var(--color-text-secondary)',
  },
  success: {
    surface: 'var(--tint-success-soft)',
    border: '1px solid var(--tint-success-soft)',
    labelColor: 'rgba(167, 243, 208, 0.82)',
    valueColor: 'var(--color-text-success-soft)',
    glow: 'var(--tint-success-soft)',
    dot: 'var(--color-icon-success)',
  },
  warn: {
    surface: 'var(--tint-warning-soft)',
    border: '1px solid var(--tint-warning-soft)',
    labelColor: 'rgba(253, 230, 138, 0.86)',
    valueColor: 'var(--color-text-warning-soft)',
    glow: 'var(--tint-warning-soft)',
    dot: 'var(--color-icon-warning)',
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

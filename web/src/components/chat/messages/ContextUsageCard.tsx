import type { ChatResponseMeta } from '../../../types';
import { formatPercent, resolveContextUsage } from '../chatUtils';

export default function ContextUsageCard({
  meta,
  fallbackContextLength,
}: {
  meta?: ChatResponseMeta;
  fallbackContextLength?: number | null;
}) {
  const usage = resolveContextUsage(meta, fallbackContextLength);
  if (!usage) {
    return null;
  }

  return (
    <div
      className="mr-6 rounded-xl p-3"
      style={{ background: 'rgba(255,255,255,0.035)', border: '1px solid rgba(255,255,255,0.08)' }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1.5 text-[12px] leading-5">
          <div style={{ color: 'var(--color-text-secondary)' }}>
            Current conversation tokens: <span className="font-semibold text-white">{usage.inputTokens}</span>
          </div>
          <div style={{ color: 'var(--color-text-secondary)' }}>
            Total loaded context: <span className="font-semibold text-white">{usage.contextLength}</span>
          </div>
          <div style={{ color: 'var(--color-text-muted)' }}>
            {formatPercent(usage.usedPercent)} used ({formatPercent(usage.remainingPercent)} left)
          </div>
        </div>
        <div className="flex min-w-[60px] flex-col items-center gap-2">
          <div
            className="relative h-11 w-11 rounded-full"
            style={{
              background: `conic-gradient(#60a5fa ${usage.usedPercent}%, rgba(255,255,255,0.08) 0)`,
            }}
          >
            <div
              className="absolute inset-[4px] flex items-center justify-center rounded-full text-[10px] font-semibold"
              style={{ background: 'var(--color-bg-surface)', color: '#93c5fd' }}
            >
              {Math.round(usage.usedPercent)}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

import type { ReactNode } from 'react';

interface StatItem {
  label: string;
  value: string | number;
}

interface Props {
  title: string;
  status: string;
  progress: number;
  subtitle?: string;
  heartbeatAt?: string | null;
  errorMessage?: string | null;
  stats?: StatItem[];
  action?: ReactNode;
}

function formatHeartbeat(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString('tr-TR');
}

export default function TaskStatusCard({
  title,
  status,
  progress,
  subtitle,
  heartbeatAt,
  errorMessage,
  stats = [],
  action,
}: Props) {
  const heartbeatLabel = formatHeartbeat(heartbeatAt);
  const tone =
    status === 'running' || status === 'analyzing'
      ? '#22c55e'
      : status === 'failed' || status === 'completed_with_errors'
        ? '#f97316'
        : status === 'cancelled' || status === 'stopped'
          ? '#ef4444'
          : '#94a3b8';

  return (
    <div
      className="rounded-2xl p-5"
      style={{
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: tone }} />
            <h3 className="text-[16px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {title}
            </h3>
          </div>
          <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            {subtitle ?? 'Birlesik task runtime durumu'}
          </p>
        </div>
        <div className="text-right">
          <div className="text-[12px] uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
            {status}
          </div>
          <div className="mt-1 text-[28px] font-bold tabular-nums" style={{ color: 'var(--color-text-primary)' }}>
            %{progress}
          </div>
        </div>
      </div>

      <div
        className="mt-4 h-2.5 overflow-hidden rounded-full"
        style={{ background: 'rgba(148,163,184,0.12)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${Math.max(0, Math.min(100, progress))}%`,
            background: `linear-gradient(90deg, ${tone}, rgba(125,211,252,0.92))`,
          }}
        />
      </div>

      {(stats.length > 0 || heartbeatLabel || action || errorMessage) && (
        <div className="mt-4 flex flex-wrap items-center gap-3 text-[12px]">
          {stats.map((stat) => (
            <div
              key={stat.label}
              className="rounded-full px-3 py-1"
              style={{
                background: 'rgba(15,23,42,0.48)',
                border: '1px solid rgba(148,163,184,0.18)',
                color: 'var(--color-text-secondary)',
              }}
            >
              <span>{stat.label}: </span>
              <strong style={{ color: 'var(--color-text-primary)' }}>{stat.value}</strong>
            </div>
          ))}
          {heartbeatLabel && (
            <div style={{ color: 'var(--color-text-muted)' }}>
              Son heartbeat: <strong style={{ color: 'var(--color-text-primary)' }}>{heartbeatLabel}</strong>
            </div>
          )}
          {action}
        </div>
      )}

      {errorMessage && (
        <div
          className="mt-4 rounded-xl px-3 py-2 text-[12px]"
          style={{
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.22)',
            color: '#fecaca',
          }}
        >
          {errorMessage}
        </div>
      )}
    </div>
  );
}

import type { BatchJob } from '../../types';

const STATUS_LABELS: Record<string, string> = {
  idle: 'Bosta',
  analyzing: 'Analiz Ediliyor',
  analyzed: 'Analiz Tamamlandi',
  running: 'Calisiyor',
  paused: 'Duraklatildi',
  completed: 'Tamamlandi',
  completed_with_errors: 'Kismi Tamamlandi',
  failed: 'Hata',
  cancelled: 'Iptal',
};

const STATUS_BG: Record<string, string> = {
  analyzing: 'var(--tint-warning-soft)',
  analyzed: 'var(--tint-primary-soft)',
  running: 'var(--tint-success-soft)',
  completed: 'var(--tint-primary-soft)',
  completed_with_errors: 'var(--tint-warning-soft)',
  failed: 'var(--tint-danger-soft)',
  cancelled: 'var(--color-border-subtle)',
  idle: 'var(--color-border-subtle)',
  paused: 'var(--tint-primary-soft)',
};

const STATUS_TEXT: Record<string, string> = {
  analyzing: 'var(--color-warning)',
  analyzed: 'var(--color-primary-light)',
  running: 'var(--color-success)',
  completed: 'var(--color-primary-light)',
  completed_with_errors: 'var(--color-warning)',
  failed: 'var(--color-danger)',
  cancelled: 'var(--color-text-secondary)',
  idle: 'var(--color-text-secondary)',
  paused: 'var(--color-primary-light)',
};

interface Props {
  jobs: BatchJob[];
  onSelect: (jobId: string, status: string) => void;
  onDelete?: (jobId: string) => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function ScoreDelta({
  before,
  after,
  projected = false,
}: {
  before: number;
  after: number;
  projected?: boolean;
}) {
  if (!before && !after) return <span style={{ color: 'var(--color-text-muted)' }}>-</span>;
  const delta = after - before;
  return (
    <span
      className="font-semibold tabular-nums"
      style={{ color: delta > 0 ? 'var(--color-success)' : delta < 0 ? 'var(--color-danger)' : 'var(--color-text-muted)' }}
    >
      {projected && <span style={{ color: 'var(--color-text-muted)' }}>Tahmini </span>}
      {before.toFixed(0)} {'->'} {after.toFixed(0)}
      {delta !== 0 && (
        <span className="ml-1 text-[10px]">
          ({delta > 0 ? '+' : ''}{delta.toFixed(1)})
        </span>
      )}
    </span>
  );
}

export default function BatchHistory({ jobs, onSelect, onDelete }: Props) {
  return (
    <div
      className="rounded-xl"
      style={{
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <h3
          className="text-[13px] font-semibold uppercase tracking-wider"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Islem Gecmisi
        </h3>
      </div>

      {jobs.length === 0 ? (
        <div className="px-4 py-8 text-center text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
          Henuz islem yapilmadi.
        </div>
      ) : (
        <div className="divide-y" style={{ borderColor: 'var(--color-border)' }}>
          {jobs.map((job) => (
            <div
              key={job.id}
              className="flex items-center gap-3 px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                    style={{
                      background: STATUS_BG[job.status] ?? STATUS_BG.idle,
                      color: STATUS_TEXT[job.status] ?? STATUS_TEXT.idle,
                    }}
                  >
                    {STATUS_LABELS[job.status] ?? job.status}
                  </span>
                  <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                    {formatDate(job.created_at)}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-3 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                  <span>{job.processed_count} islendi</span>
                  {job.skipped_count > 0 && <span>{job.skipped_count} atlandi</span>}
                  {(job.avg_score_before > 0 || job.avg_score_after > 0) && (
                    <ScoreDelta
                      before={job.avg_score_before}
                      after={job.avg_score_after}
                      projected={job.status !== 'completed' && job.status !== 'completed_with_errors'}
                    />
                  )}
                </div>
              </div>
              <div className="flex flex-shrink-0 items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => onSelect(job.id, job.status)}
                  className="rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors hover:bg-[var(--color-bg-hover)]"
                  style={{ color: 'var(--color-primary-light)', border: '1px solid var(--color-border-primary)' }}
                >
                  Detay
                </button>
                {onDelete && job.status !== 'running' && job.status !== 'analyzing' && (
                  <button
                    type="button"
                    onClick={() => onDelete(job.id)}
                    className="rounded-lg px-2 py-1 text-[11px] font-medium transition-colors hover:bg-[var(--tint-danger-soft)]"
                    style={{ color: 'var(--color-danger)', border: '1px solid var(--tint-danger-soft)' }}
                    title="Sil"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

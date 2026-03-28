import type { BatchJob } from '../../types';

const STATUS_LABELS: Record<string, string> = {
  idle: 'Boşta',
  analyzing: 'Analiz Ediliyor',
  analyzed: 'Analiz Tamamlandı',
  running: 'Çalışıyor',
  paused: 'Duraklatıldı',
  completed: 'Tamamlandı',
  completed_with_errors: 'Kısmi Tamamlandı',
  failed: 'Hata',
  cancelled: 'İptal',
};

const STATUS_BG: Record<string, string> = {
  analyzing: 'rgba(245,158,11,0.15)',
  analyzed: 'rgba(99,102,241,0.15)',
  running: 'rgba(34,197,94,0.15)',
  completed: 'rgba(99,102,241,0.15)',
  completed_with_errors: 'rgba(245,158,11,0.15)',
  failed: 'rgba(239,68,68,0.15)',
  cancelled: 'rgba(100,116,139,0.15)',
  idle: 'rgba(100,116,139,0.15)',
  paused: 'rgba(99,102,241,0.15)',
};

const STATUS_TEXT: Record<string, string> = {
  analyzing: '#f59e0b',
  analyzed: '#818cf8',
  running: '#22c55e',
  completed: '#818cf8',
  completed_with_errors: '#f59e0b',
  failed: '#ef4444',
  cancelled: '#94a3b8',
  idle: '#94a3b8',
  paused: '#818cf8',
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

function ScoreDelta({ before, after }: { before: number; after: number }) {
  if (!before && !after) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>;
  const delta = after - before;
  return (
    <span
      className="font-semibold tabular-nums"
      style={{ color: delta > 0 ? '#22c55e' : delta < 0 ? '#ef4444' : 'var(--color-text-muted)' }}
    >
      {before.toFixed(0)} → {after.toFixed(0)}
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
          İşlem Geçmişi
        </h3>
      </div>

      {jobs.length === 0 ? (
        <div className="px-4 py-8 text-center text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
          Henüz işlem yapılmadı.
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
                  <span>{job.processed_count} işlendi</span>
                  {job.skipped_count > 0 && <span>{job.skipped_count} atlandı</span>}
                  {(job.avg_score_before > 0 || job.avg_score_after > 0) && (
                    <ScoreDelta before={job.avg_score_before} after={job.avg_score_after} />
                  )}
                </div>
              </div>
              <div className="flex flex-shrink-0 items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => onSelect(job.id, job.status)}
                  className="rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors hover:bg-[var(--color-bg-hover)]"
                  style={{ color: 'var(--color-primary-light)', border: '1px solid rgba(99,102,241,0.25)' }}
                >
                  Detay
                </button>
                {onDelete && job.status !== 'running' && job.status !== 'analyzing' && (
                  <button
                    type="button"
                    onClick={() => onDelete(job.id)}
                    className="rounded-lg px-2 py-1 text-[11px] font-medium transition-colors hover:bg-[rgba(239,68,68,0.1)]"
                    style={{ color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}
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

import { useEffect, useRef, useState } from 'react';
import type { BatchJob, BatchItem } from '../../types';
import ProgressBar from '../../shared/ui/ProgressBar';
import ConfirmDialog from '../../shared/ui/ConfirmDialog';
import { createBatchJobStream } from '../../api/client';

interface ProgressEvent {
  type: 'progress' | 'completed' | 'error';
  job: BatchJob;
}

interface Props {
  job: BatchJob;
  onStop: () => void;
  onJobComplete: (jobId: string) => void;
}

function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) return null;
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[10px] font-bold tabular-nums"
      style={{
        background: delta > 0 ? 'rgba(34,197,94,0.15)' : delta < 0 ? 'rgba(239,68,68,0.15)' : 'rgba(100,116,139,0.15)',
        color: delta > 0 ? '#22c55e' : delta < 0 ? '#ef4444' : '#94a3b8',
      }}
    >
      {delta > 0 ? '+' : ''}{delta}
    </span>
  );
}

export default function BatchProgressView({ job, onStop, onJobComplete }: Props) {
  const [liveJob, setLiveJob] = useState<BatchJob>(job);
  const [eventLog, setEventLog] = useState<BatchItem[]>([]);
  const [showStopConfirm, setShowStopConfirm] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (esRef.current) {
      esRef.current.close();
    }
    const es = createBatchJobStream(job.id);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data: ProgressEvent = JSON.parse(e.data);
        if (data.job) {
          setLiveJob(data.job);
        }
        if (data.type === 'completed') {
          es.close();
          onJobComplete(job.id);
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [job.id, onJobComplete]);

  const pct = liveJob.total_count > 0
    ? Math.round((liveJob.processed_count / liveJob.total_count) * 100)
    : 0;

  const isRunning = liveJob.status === 'running' || liveJob.status === 'calibrating';

  return (
    <div className="space-y-5">
      {/* Main progress card */}
      <div
        className="rounded-xl p-5"
        style={{
          background: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              {isRunning && (
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    background: '#22c55e',
                    animation: 'pulse 2s infinite',
                  }}
                />
              )}
              <h2 className="text-[16px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
                Otonom SEO Optimizasyonu
              </h2>
            </div>
            <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              İşlenen:{' '}
              <span className="font-semibold tabular-nums" style={{ color: 'var(--color-text-primary)' }}>
                {liveJob.processed_count}
              </span>
              {' / '}
              <span className="tabular-nums">{liveJob.total_count}</span>
              {liveJob.skipped_count > 0 && (
                <span className="ml-3">
                  Atlanan:{' '}
                  <span className="font-semibold tabular-nums" style={{ color: '#f59e0b' }}>
                    {liveJob.skipped_count}
                  </span>
                </span>
              )}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[28px] font-bold tabular-nums" style={{ color: 'var(--color-text-primary)' }}>
              %{pct}
            </p>
            {isRunning && (
              <button
                type="button"
                onClick={() => setShowStopConfirm(true)}
                className="mt-1 rounded-lg px-3 py-1 text-[11px] font-medium transition-colors hover:bg-[var(--color-bg-hover)]"
                style={{
                  border: '1px solid rgba(239,68,68,0.3)',
                  color: '#ef4444',
                }}
              >
                İşlemi Durdur
              </button>
            )}
          </div>
        </div>

        <ProgressBar pct={pct} animated height="h-2.5" />

        {/* Score improvement */}
        {liveJob.avg_score_before > 0 && liveJob.avg_score_after > 0 && (
          <div className="mt-3 flex items-center gap-2 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            <span>Ort. skor:</span>
            <span className="tabular-nums font-medium" style={{ color: 'var(--color-text-primary)' }}>
              {liveJob.avg_score_before.toFixed(0)} → {liveJob.avg_score_after.toFixed(0)}
            </span>
            <DeltaBadge delta={Math.round(liveJob.avg_score_after - liveJob.avg_score_before)} />
          </div>
        )}
      </div>

      {/* Event log */}
      {eventLog.length > 0 && (
        <div
          className="rounded-xl overflow-hidden"
          style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--color-border)' }}>
            <p className="text-[12px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Canlı Akış
            </p>
          </div>
          <div className="divide-y" style={{ borderColor: 'var(--color-border)' }}>
            {eventLog.slice(0, 20).map((item) => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-2.5">
                <span
                  className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
                  style={{
                    background: item.status === 'applied' || item.status === 'approved'
                      ? '#22c55e'
                      : item.status === 'failed' || item.status === 'skipped'
                      ? '#ef4444'
                      : '#94a3b8',
                  }}
                />
                <span className="min-w-0 flex-1 truncate text-[12px]" style={{ color: 'var(--color-text-primary)' }}>
                  {item.product_name}
                </span>
                <div className="flex flex-shrink-0 items-center gap-1.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                  {item.score_before !== null && <span className="tabular-nums">{item.score_before}</span>}
                  {item.score_after !== null && (
                    <>
                      <span>→</span>
                      <span className="tabular-nums font-medium" style={{ color: 'var(--color-text-primary)' }}>
                        {item.score_after}
                      </span>
                    </>
                  )}
                  {item.score_before !== null && item.score_after !== null && (
                    <DeltaBadge delta={item.score_after - item.score_before} />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Completion state */}
      {liveJob.status === 'completed' && (
        <div
          className="rounded-xl p-5 text-center"
          style={{
            background: 'rgba(34,197,94,0.05)',
            border: '1px solid rgba(34,197,94,0.2)',
          }}
        >
          <p className="text-[15px] font-semibold" style={{ color: '#22c55e' }}>
            Otonom Optimizasyon Döngüsü Tamamlandı
          </p>
          <div className="mt-2 flex justify-center gap-6 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            <span>İşlenen Ürün: <strong style={{ color: 'var(--color-text-primary)' }}>{liveJob.processed_count}</strong></span>
            <span>Atlanan: <strong style={{ color: 'var(--color-text-primary)' }}>{liveJob.skipped_count}</strong></span>
            {liveJob.avg_score_before > 0 && (
              <span>
                Ort. Artış:{' '}
                <strong style={{ color: '#22c55e' }}>
                  +{(liveJob.avg_score_after - liveJob.avg_score_before).toFixed(1)}
                </strong>
              </span>
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={showStopConfirm}
        title="İşlemi Durdur"
        message="Toplu optimizasyon durdurulacak. Tamamlanan ürünler kaydedilecektir. Devam etmek istiyor musunuz?"
        confirmLabel="Durdur"
        cancelLabel="İptal"
        variant="danger"
        onConfirm={() => { setShowStopConfirm(false); onStop(); }}
        onCancel={() => setShowStopConfirm(false)}
      />
    </div>
  );
}

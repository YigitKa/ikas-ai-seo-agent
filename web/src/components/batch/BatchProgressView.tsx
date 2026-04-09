import { useEffect, useRef, useState } from 'react';
import type { BatchFeedbackEvent, BatchJob } from '../../types';
import ProgressBar from '../../shared/ui/ProgressBar';
import ConfirmDialog from '../../shared/ui/ConfirmDialog';
import { createBatchJobStream } from '../../api/client';
import TaskStatusCard from '../tasks/TaskStatusCard';

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

function formatEventTime(value?: string | null): string {
  if (!value) return 'Az once';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return 'Az once';
  return parsed.toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatEta(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return 'Tahmin yok';
  if (seconds <= 0) return 'Tamamlandi';
  if (seconds < 60) return `${seconds} sn`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes} dk ${remainingSeconds} sn`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours} sa ${remainingMinutes} dk`;
}

function InfoCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string | null;
}) {
  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: 'rgba(15,23,42,0.28)',
        border: '1px solid rgba(148,163,184,0.14)',
      }}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
        {label}
      </p>
      <p className="mt-1 text-[14px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
        {value}
      </p>
      {sub && (
        <p className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          {sub}
        </p>
      )}
    </div>
  );
}

function EventRow({ event }: { event: BatchFeedbackEvent }) {
  return (
    <div
      className="rounded-xl px-3 py-2.5"
      style={{
        background: 'rgba(15,23,42,0.28)',
        border: '1px solid rgba(148,163,184,0.14)',
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {event.message}
          </p>
          {(event.product_name || event.reason_code || event.user_message) && (
            <p className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {[event.product_name, event.user_message, event.reason_code ? `Kod: ${event.reason_code}` : null].filter(Boolean).join(' · ')}
            </p>
          )}
        </div>
        <span className="shrink-0 text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
          {formatEventTime(event.at)}
        </span>
      </div>
    </div>
  );
}

export default function BatchProgressView({ job, onStop, onJobComplete }: Props) {
  const [liveJob, setLiveJob] = useState<BatchJob>(job);
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
          if (data.job?.status !== 'analyzed') {
            onJobComplete(job.id);
          }
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

  const feedback = liveJob.feedback;
  const counts = feedback.summary_counts;
  const pct = counts.total > 0 ? Math.round((counts.processed / counts.total) * 100) : 0;
  const isRunning = liveJob.status === 'running' || liveJob.status === 'analyzing';
  const avgDelta = liveJob.avg_score_before > 0 && liveJob.avg_score_after > 0
    ? Math.round(liveJob.avg_score_after - liveJob.avg_score_before)
    : null;
  const recentEvents = feedback.recent_events.slice(0, 5);
  const currentItem = feedback.current_item;
  const lastItem = feedback.last_completed_item;

  return (
    <div className="space-y-5">
      <TaskStatusCard
        title="Batch gorevi"
        status={liveJob.status}
        progress={pct}
        subtitle={feedback.status_message || 'Analiz ve uygulama adimlari ortak task semantigiyle izleniyor'}
        heartbeatAt={feedback.heartbeat_at}
        errorMessage={liveJob.error}
        stats={[
          { label: 'Faz', value: feedback.stage_label || 'Hazirlaniyor' },
          { label: 'Islenen', value: `${counts.processed}/${counts.total}` },
          { label: 'Basarili', value: counts.succeeded },
          { label: 'Atlanan', value: counts.skipped },
          { label: 'Hatali', value: counts.failed },
          { label: 'ETA', value: formatEta(feedback.eta_seconds) },
        ]}
        action={isRunning ? (
          <button
            type="button"
            onClick={() => setShowStopConfirm(true)}
            className="rounded-lg px-3 py-1 text-[11px] font-medium transition-colors hover:bg-[var(--color-bg-hover)]"
            style={{
              border: '1px solid rgba(239,68,68,0.3)',
              color: '#ef4444',
            }}
          >
            Islemi Durdur
          </button>
        ) : undefined}
      />

      <div
        className="rounded-xl p-5"
        style={{
          background: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
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
                {feedback.stage_label || 'Toplu Islem'}
              </h2>
            </div>
            <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              {feedback.status_message || 'Islem durumu guncelleniyor.'}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[28px] font-bold tabular-nums" style={{ color: 'var(--color-text-primary)' }}>
              %{pct}
            </p>
            <p className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {counts.processed}/{counts.total} urun ele alindi
            </p>
          </div>
        </div>

        <ProgressBar pct={pct} animated={isRunning} height="h-2.5" />

        <div className="mt-4 grid grid-cols-3 gap-3">
          <InfoCard
            label="Su An"
            value={currentItem?.product_name || 'Beklemede'}
            sub={currentItem?.user_message || feedback.status_message}
          />
          <InfoCard
            label="Son Tamamlanan"
            value={lastItem?.product_name || 'Henuz yok'}
            sub={lastItem?.user_message || null}
          />
          <InfoCard
            label="Son Olay"
            value={feedback.latest_event?.message || 'Bekleniyor'}
            sub={feedback.latest_event ? `${formatEventTime(feedback.latest_event.at)} · ETA ${formatEta(feedback.eta_seconds)}` : `ETA ${formatEta(feedback.eta_seconds)}`}
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px]">
          <span className="rounded-full px-3 py-1" style={{ background: 'rgba(34,197,94,0.12)', color: '#22c55e' }}>
            Basarili: <strong>{counts.succeeded}</strong>
          </span>
          <span className="rounded-full px-3 py-1" style={{ background: 'rgba(245,158,11,0.12)', color: '#f59e0b' }}>
            Atlanan: <strong>{counts.skipped}</strong>
          </span>
          <span className="rounded-full px-3 py-1" style={{ background: 'rgba(239,68,68,0.12)', color: '#ef4444' }}>
            Hatali: <strong>{counts.failed}</strong>
          </span>
          {avgDelta !== null && (
            <span className="rounded-full px-3 py-1" style={{ background: 'rgba(125,211,252,0.12)', color: '#7dd3fc' }}>
              Ort. skor degisimi <DeltaBadge delta={avgDelta} />
            </span>
          )}
        </div>

        {feedback.next_action_hints.length > 0 && (
          <div className="mt-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
              Sonraki Adim
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {feedback.next_action_hints.map((hint) => (
                <span
                  key={hint}
                  className="rounded-full px-3 py-1 text-[11px]"
                  style={{
                    background: 'rgba(148,163,184,0.12)',
                    color: 'var(--color-text-secondary)',
                    border: '1px solid rgba(148,163,184,0.14)',
                  }}
                >
                  {hint}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div
        className="rounded-xl p-5"
        style={{
          background: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[13px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
            Son Olaylar
          </h3>
          <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
            Son guncelleme {formatEventTime(feedback.last_event_at)}
          </span>
        </div>

        {recentEvents.length > 0 ? (
          <div className="space-y-2">
            {recentEvents.map((event) => (
              <EventRow key={`${event.sequence}:${event.type}`} event={event} />
            ))}
          </div>
        ) : (
          <p className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            Henuz gosterilecek olay yok.
          </p>
        )}
      </div>

      {(liveJob.status === 'completed' || liveJob.status === 'completed_with_errors') && (
        <div
          className="rounded-xl p-5"
          style={{
            background: liveJob.status === 'completed'
              ? 'rgba(34,197,94,0.05)'
              : 'rgba(249,115,22,0.06)',
            border: liveJob.status === 'completed'
              ? '1px solid rgba(34,197,94,0.2)'
              : '1px solid rgba(249,115,22,0.22)',
          }}
        >
          <p
            className="text-[15px] font-semibold"
            style={{ color: liveJob.status === 'completed' ? '#22c55e' : '#f97316' }}
          >
            {liveJob.status === 'completed' ? 'Toplu Islem Tamamlandi' : 'Toplu Islem Hata Ile Tamamlandi'}
          </p>
          <div className="mt-2 flex flex-wrap gap-5 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            <span>Basarili: <strong style={{ color: 'var(--color-text-primary)' }}>{counts.succeeded}</strong></span>
            <span>Atlanan: <strong style={{ color: 'var(--color-text-primary)' }}>{counts.skipped}</strong></span>
            <span>Hatali: <strong style={{ color: 'var(--color-text-primary)' }}>{counts.failed}</strong></span>
            {avgDelta !== null && (
              <span>
                Ort. Artis:{' '}
                <strong style={{ color: avgDelta >= 0 ? '#22c55e' : '#ef4444' }}>
                  {avgDelta > 0 ? '+' : ''}{avgDelta}
                </strong>
              </span>
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={showStopConfirm}
        title="Islemi Durdur"
        message="Toplu optimizasyon durdurulacak. Tamamlanan urunler kaydedilecektir. Devam etmek istiyor musunuz?"
        confirmLabel="Durdur"
        cancelLabel="Iptal"
        variant="danger"
        onConfirm={() => { setShowStopConfirm(false); onStop(); }}
        onCancel={() => setShowStopConfirm(false)}
      />
    </div>
  );
}

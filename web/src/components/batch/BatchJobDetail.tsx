import { useState } from 'react';
import type { BatchFeedbackEvent, BatchItem, BatchJob } from '../../types';
import ConfirmDialog from '../../shared/ui/ConfirmDialog';

const ITEM_STATUS_LABELS: Record<string, string> = {
  pending: 'Bekliyor',
  analyzed: 'Analiz Edildi',
  processing: 'Isleniyor',
  approved: 'Onaylandi',
  rejected: 'Reddedildi',
  applied: 'Uygulandi',
  skipped: 'Atlandi',
  failed: 'Hata',
  rolled_back: 'Geri Alindi',
};

const ITEM_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  applied: { bg: 'var(--tint-success-soft)', text: 'var(--color-success)' },
  approved: { bg: 'var(--tint-primary-soft)', text: 'var(--color-primary-light)' },
  analyzed: { bg: 'var(--tint-warning-soft)', text: 'var(--color-warning)' },
  skipped: { bg: 'var(--tint-warning-soft)', text: 'var(--color-warning)' },
  failed: { bg: 'var(--tint-danger-soft)', text: 'var(--color-danger)' },
  rolled_back: { bg: 'var(--color-border-subtle)', text: 'var(--color-text-secondary)' },
  pending: { bg: 'rgba(100,116,139,0.1)', text: 'var(--color-text-secondary)' },
  processing: { bg: 'var(--tint-primary-soft)', text: 'var(--color-primary-light)' },
  rejected: { bg: 'var(--tint-danger-soft)', text: 'var(--color-danger)' },
};

type ItemFilter = 'all' | 'processing' | 'failed' | 'skipped' | 'approved' | 'applied';

const FILTERS: Array<{ id: ItemFilter; label: string }> = [
  { id: 'all', label: 'Tum' },
  { id: 'processing', label: 'Isleniyor' },
  { id: 'failed', label: 'Hatali' },
  { id: 'skipped', label: 'Atlanan' },
  { id: 'approved', label: 'Onayli' },
  { id: 'applied', label: 'Uygulandi' },
];

interface Props {
  job: BatchJob;
  items: BatchItem[];
  onRollbackItem: (itemId: number) => void;
  onRollbackAll: () => void;
  onBack: () => void;
  isRollingBack: boolean;
}

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatShortDate(iso?: string | null): string {
  if (!iso) return 'Az once';
  const parsed = new Date(iso);
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

function ScoreDeltaCell({ before, after }: { before: number | null; after: number | null }) {
  if (before === null && after === null) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>;
  const delta = before !== null && after !== null ? after - before : null;
  return (
    <div className="flex items-center gap-1.5 text-[12px]">
      {before !== null && <span className="tabular-nums" style={{ color: 'var(--color-text-muted)' }}>{before}</span>}
      {after !== null && (
        <>
          <span style={{ color: 'var(--color-text-muted)' }}>→</span>
          <span className="font-semibold tabular-nums" style={{ color: 'var(--color-text-primary)' }}>{after}</span>
        </>
      )}
      {delta !== null && (
        <span
          className="rounded px-1 py-0.5 text-[10px] font-bold"
          style={{
            background: delta > 0 ? 'var(--tint-success-soft)' : delta < 0 ? 'var(--tint-danger-soft)' : 'var(--color-border-subtle)',
            color: delta > 0 ? 'var(--color-success)' : delta < 0 ? 'var(--color-danger)' : 'var(--color-text-secondary)',
          }}
        >
          {delta > 0 ? '+' : ''}{delta}
        </span>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string;
  sub?: string | null;
  highlight?: string;
}) {
  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
      }}
    >
      <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
        {label}
      </p>
      <p className="mt-1 text-[18px] font-bold" style={{ color: highlight ?? 'var(--color-text-primary)' }}>
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

function EventCard({ event }: { event: BatchFeedbackEvent }) {
  return (
    <div
      className="rounded-xl px-3 py-2.5"
      style={{
        background: 'var(--surface-card)',
        border: '1px solid var(--color-divider)',
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {event.message}
          </p>
          {(event.product_name || event.user_message || event.reason_code) && (
            <p className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {[event.product_name, event.user_message, event.reason_code ? `Kod: ${event.reason_code}` : null].filter(Boolean).join(' · ')}
            </p>
          )}
        </div>
        <span className="shrink-0 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          {formatShortDate(event.at)}
        </span>
      </div>
    </div>
  );
}

export default function BatchJobDetail({ job, items, onRollbackItem, onRollbackAll, onBack, isRollingBack }: Props) {
  const [rollbackItemId, setRollbackItemId] = useState<number | null>(null);
  const [showRollbackAll, setShowRollbackAll] = useState(false);
  const [itemFilter, setItemFilter] = useState<ItemFilter>('all');

  const feedback = job.feedback;
  const hasAnyRollback = items.some((i) => i.has_rollback);
  const hasAppliedChanges = items.some((i) => i.status === 'applied' || i.status === 'rolled_back');
  const appliedCount = items.filter((i) => i.status === 'applied' || i.status === 'approved').length;
  const avgBefore = job.avg_score_before;
  const avgAfter = job.avg_score_after;
  const hasScoreSignal = avgBefore > 0 || avgAfter > 0;
  const avgDelta = hasScoreSignal ? avgAfter - avgBefore : null;
  const projectedScore = !hasAppliedChanges;
  const resumable = job.status === 'failed' || job.status === 'cancelled';
  const lastProcessed = feedback.last_completed_item;
  const lastError = feedback.recent_events.find((event) => event.type === 'item_failed' || event.type === 'operation_failed') ?? null;
  const lastSkipped = feedback.recent_events.find((event) => event.type === 'item_skipped') ?? null;
  const recentEvents = feedback.recent_events.slice(0, 6);
  const successLabel = hasAppliedChanges
    ? 'Uygulanan Urun'
    : feedback.stage === 'awaiting_review' || job.status === 'analyzed' || feedback.stage === 'analyzing'
      ? 'Analiz Edilen Urun'
      : 'Islenen Urun';
  const scoreLabel = projectedScore ? 'Tahmini Skor Degisimi' : 'Ort. Skor Degisimi';
  const scoreSub = projectedScore
    ? (job.status === 'failed'
      ? 'Islem uygulanmadan durdu; skor farki analiz tahminidir.'
      : 'Skor farki analiz sonucundan hesaplandi.')
    : (job.completed_at ? `Tamamlanma ${formatDate(job.completed_at)}` : 'Islem tamamlanmadi');
  const scoreColumnLabel = projectedScore ? 'Tahmini Skor' : 'Skor Degisimi';
  const lastProcessedLabel = projectedScore ? 'Son Analiz Edilen Urun' : 'Son Islenen Urun';

  const filterCounts: Record<ItemFilter, number> = {
    all: items.length,
    processing: items.filter((item) => item.status === 'processing').length,
    failed: items.filter((item) => item.status === 'failed').length,
    skipped: items.filter((item) => item.status === 'skipped').length,
    approved: items.filter((item) => item.status === 'approved').length,
    applied: items.filter((item) => item.status === 'applied').length,
  };

  const filteredItems = items.filter((item) => {
    if (itemFilter === 'all') return true;
    return item.status === itemFilter;
  });

  const issueMap = new Map<string, { label: string; count: number }>();
  for (const item of items) {
    if (item.status !== 'failed' && item.status !== 'skipped') continue;
    const label = item.skip_reason?.trim() || ITEM_STATUS_LABELS[item.status] || item.status;
    const key = `${item.status}:${label}`;
    const current = issueMap.get(key);
    if (current) current.count += 1;
    else issueMap.set(key, { label, count: 1 });
  }
  const issueGroups = Array.from(issueMap.values()).sort((a, b) => b.count - a.count).slice(0, 5);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-[13px] font-medium transition-opacity hover:opacity-70"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Gecmis
        </button>
        {hasAnyRollback && (
          <button
            type="button"
            onClick={() => setShowRollbackAll(true)}
            disabled={isRollingBack}
            className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors hover:bg-[var(--color-bg-hover)] disabled:opacity-40"
            style={{
              border: '1px solid var(--color-border-danger)',
              color: 'var(--color-danger)',
            }}
          >
            Tum Islemi Geri Al
          </button>
        )}
      </div>

      <div className="grid grid-cols-5 gap-4">
        <SummaryCard
          label="Mevcut Faz"
          value={feedback.stage_label || 'Hazirlaniyor'}
          sub={feedback.status_message || null}
        />
        <SummaryCard
          label={lastProcessedLabel}
          value={lastProcessed?.product_name || 'Henuz yok'}
          sub={lastProcessed?.user_message || null}
        />
        <SummaryCard
          label="Son Hata"
          value={lastError?.product_name || (lastError ? 'Is Hatasi' : 'Hata yok')}
          sub={lastError?.user_message || lastError?.reason_code || job.error || null}
          highlight={lastError ? 'var(--color-danger)' : undefined}
        />
        <SummaryCard
          label="Son Atlama"
          value={lastSkipped?.product_name || 'Atlama yok'}
          sub={lastSkipped?.user_message || lastSkipped?.reason_code || null}
          highlight={lastSkipped ? 'var(--color-warning)' : undefined}
        />
        <SummaryCard
          label="Durum"
          value={resumable ? 'Devam Ettirilebilir' : 'Terminal'}
          sub={`Son guncelleme ${formatDate(feedback.last_event_at || job.updated_at)} · ETA ${formatEta(feedback.eta_seconds)}`}
        />
      </div>

      {job.error && (
        <div
          className="rounded-xl p-4"
          style={{
            background: 'var(--tint-danger-bg)',
            border: '1px solid var(--color-border-danger)',
          }}
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-danger-soft)' }}>
            Is Hatasi
          </p>
          <p className="mt-2 text-[12px]" style={{ color: 'var(--color-text-danger-soft)' }}>
            {job.error}
          </p>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        <SummaryCard label={successLabel} value={`${feedback.summary_counts.succeeded}`} />
        <SummaryCard label="Atlanan Urun" value={`${feedback.summary_counts.skipped}`} sub={lastSkipped?.user_message || 'Son atlama nedeni burada gorunur'} />
        <SummaryCard label="Hatali Urun" value={`${feedback.summary_counts.failed}`} sub={lastError?.user_message || job.error || 'Son hata burada gorunur'} highlight={feedback.summary_counts.failed > 0 || job.status === 'failed' ? 'var(--color-danger)' : undefined} />
        <SummaryCard
          label={scoreLabel}
          value={avgDelta === null ? '-' : avgDelta > 0 ? `+${avgDelta.toFixed(1)}` : avgDelta.toFixed(1)}
          sub={scoreSub}
          highlight={avgDelta !== null && !projectedScore && avgDelta > 0 ? 'var(--color-success)' : undefined}
        />
      </div>

      {feedback.next_action_hints.length > 0 && (
        <div
          className="rounded-xl p-4"
          style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border)',
          }}
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
            Sonraki Adimlar
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {feedback.next_action_hints.map((hint) => (
              <span
                key={hint}
                className="rounded-full px-3 py-1 text-[11px]"
                style={{
                  background: 'var(--color-divider)',
                  color: 'var(--color-text-secondary)',
                  border: '1px solid var(--color-border-subtle)',
                }}
              >
                {hint}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-5">
        <div
          className="rounded-xl p-4"
          style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div className="flex items-center justify-between">
            <p className="text-[12px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
              Son Olaylar
            </p>
            <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              Son event {formatShortDate(feedback.last_event_at)}
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {recentEvents.length > 0 ? recentEvents.map((event) => (
              <EventCard key={`${event.sequence}:${event.type}`} event={event} />
            )) : (
              <p className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                Gosterilecek event yok.
              </p>
            )}
          </div>
        </div>

        <div
          className="rounded-xl p-4"
          style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div className="flex items-center justify-between">
            <p className="text-[12px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
              Hata ve Atlama Ozeti
            </p>
            <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {issueGroups.length} grup
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {issueGroups.length > 0 ? issueGroups.map((group) => (
              <div
                key={`${group.label}:${group.count}`}
                className="rounded-xl px-3 py-2.5"
                style={{
                  background: 'var(--surface-card)',
                  border: '1px solid var(--color-divider)',
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-[12px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                    {group.label}
                  </p>
                  <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ background: 'var(--color-divider)', color: 'var(--color-text-secondary)' }}>
                    {group.count}
                  </span>
                </div>
              </div>
            )) : (
              <p className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                Hata veya atlama ozetine girecek kayit yok.
              </p>
            )}
          </div>
        </div>
      </div>

      <div
        className="overflow-hidden rounded-xl"
        style={{
          background: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div
          className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
          style={{ borderBottom: '1px solid var(--color-border)' }}
        >
          <p className="text-[12px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            Islenen Urunler ({filteredItems.length}/{items.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((filter) => {
              const active = itemFilter === filter.id;
              return (
                <button
                  key={filter.id}
                  type="button"
                  onClick={() => setItemFilter(filter.id)}
                  className="rounded-full px-3 py-1 text-[11px] font-medium transition-colors"
                  style={{
                    background: active ? 'var(--tint-primary-soft)' : 'var(--color-divider)',
                    color: active ? 'var(--color-text-brand-soft)' : 'var(--color-text-secondary)',
                    border: active ? '1px solid var(--color-border-primary)' : '1px solid var(--color-divider)',
                  }}
                >
                  {filter.label} ({filterCounts[filter.id]})
                </button>
              );
            })}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Urun Adi', scoreColumnLabel, 'Durum', 'Gerekce', 'Eylem'].map((col) => (
                  <th
                    key={col}
                    className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => {
                const sc = ITEM_STATUS_COLORS[item.status] ?? ITEM_STATUS_COLORS.pending;
                return (
                  <tr key={item.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td className="px-4 py-3">
                      <p className="max-w-[220px] truncate text-[13px]" style={{ color: 'var(--color-text-primary)' }}>
                        {item.product_name}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <ScoreDeltaCell before={item.score_before} after={item.score_after} />
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{ background: sc.bg, color: sc.text }}
                      >
                        {ITEM_STATUS_LABELS[item.status] ?? item.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                        {item.skip_reason || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {item.has_rollback && item.status !== 'rolled_back' && (
                        <button
                          type="button"
                          onClick={() => setRollbackItemId(item.id)}
                          disabled={isRollingBack}
                          className="rounded px-2.5 py-1 text-[11px] font-medium transition-colors hover:bg-[var(--color-bg-hover)] disabled:opacity-40"
                          style={{
                            border: '1px solid var(--color-border-danger)',
                            color: 'var(--color-danger)',
                          }}
                        >
                          Onceki Surume Don
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {filteredItems.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                    Secili filtre icin kayit yok.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog
        open={rollbackItemId !== null}
        title="Onceki Surume Don"
        message="Bu urun icin yapilan degisiklikler geri alinacak ve orijinal icerik IKAS'a geri yuklenecektir. Devam etmek istiyor musunuz?"
        confirmLabel="Geri Al"
        cancelLabel="Iptal"
        variant="danger"
        onConfirm={() => {
          if (rollbackItemId !== null) onRollbackItem(rollbackItemId);
          setRollbackItemId(null);
        }}
        onCancel={() => setRollbackItemId(null)}
      />

      <ConfirmDialog
        open={showRollbackAll}
        title="Tum Islemi Geri Al"
        message={`Bu isteki ${appliedCount} urun icin yapilan tum degisiklikler geri alinacak. Bu islem geri alinamaz. Devam etmek istiyor musunuz?`}
        confirmLabel="Tum Degisiklikleri Geri Al"
        cancelLabel="Iptal"
        variant="danger"
        onConfirm={() => { setShowRollbackAll(false); onRollbackAll(); }}
        onCancel={() => setShowRollbackAll(false)}
      />
    </div>
  );
}

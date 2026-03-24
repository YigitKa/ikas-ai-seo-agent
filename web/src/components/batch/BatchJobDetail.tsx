import { useState } from 'react';
import type { BatchItem, BatchJob } from '../../types';
import ConfirmDialog from '../../shared/ui/ConfirmDialog';

const ITEM_STATUS_LABELS: Record<string, string> = {
  calibration: 'Kalibrasyon',
  pending: 'Bekliyor',
  processing: 'İşleniyor',
  approved: 'Onaylandı',
  rejected: 'Reddedildi',
  applied: 'Uygulandı',
  skipped: 'Atlandı',
  failed: 'Hata',
  rolled_back: 'Geri Alındı',
};

const ITEM_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  applied: { bg: 'rgba(34,197,94,0.15)', text: '#22c55e' },
  approved: { bg: 'rgba(99,102,241,0.15)', text: '#818cf8' },
  skipped: { bg: 'rgba(245,158,11,0.15)', text: '#f59e0b' },
  failed: { bg: 'rgba(239,68,68,0.15)', text: '#ef4444' },
  rolled_back: { bg: 'rgba(100,116,139,0.15)', text: '#94a3b8' },
  pending: { bg: 'rgba(100,116,139,0.1)', text: '#94a3b8' },
  processing: { bg: 'rgba(99,102,241,0.15)', text: '#818cf8' },
  rejected: { bg: 'rgba(239,68,68,0.12)', text: '#ef4444' },
  calibration: { bg: 'rgba(245,158,11,0.12)', text: '#f59e0b' },
};

interface Props {
  job: BatchJob;
  items: BatchItem[];
  onRollbackItem: (itemId: number) => void;
  onRollbackAll: () => void;
  onBack: () => void;
  isRollingBack: boolean;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
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
            background: delta > 0 ? 'rgba(34,197,94,0.15)' : delta < 0 ? 'rgba(239,68,68,0.15)' : 'rgba(100,116,139,0.12)',
            color: delta > 0 ? '#22c55e' : delta < 0 ? '#ef4444' : '#94a3b8',
          }}
        >
          {delta > 0 ? '+' : ''}{delta}
        </span>
      )}
    </div>
  );
}

export default function BatchJobDetail({ job, items, onRollbackItem, onRollbackAll, onBack, isRollingBack }: Props) {
  const [rollbackItemId, setRollbackItemId] = useState<number | null>(null);
  const [showRollbackAll, setShowRollbackAll] = useState(false);

  const hasAnyRollback = items.some((i) => i.has_rollback);
  const appliedCount = items.filter((i) => i.status === 'applied' || i.status === 'approved').length;
  const avgBefore = job.avg_score_before;
  const avgAfter = job.avg_score_after;
  const avgDelta = avgAfter - avgBefore;

  return (
    <div className="space-y-5">
      {/* Back + header */}
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
          Geçmiş
        </button>
        {hasAnyRollback && (
          <button
            type="button"
            onClick={() => setShowRollbackAll(true)}
            disabled={isRollingBack}
            className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors hover:bg-[var(--color-bg-hover)] disabled:opacity-40"
            style={{
              border: '1px solid rgba(239,68,68,0.3)',
              color: '#ef4444',
            }}
          >
            Tüm İşlemi Geri Al
          </button>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'İşlenen Ürün', value: `${job.processed_count}` },
          { label: 'Atlanan Ürün', value: `${job.skipped_count}`, sub: job.skipped_count > 0 ? 'eksik veri veya hata' : undefined },
          {
            label: 'Ort. Skor Artışı',
            value: avgDelta > 0 ? `+${avgDelta.toFixed(1)}` : avgDelta.toFixed(1),
            highlight: avgDelta > 0 ? '#22c55e' : undefined,
          },
          {
            label: 'Tamamlanma',
            value: job.completed_at ? formatDate(job.completed_at) : '—',
          },
        ].map(({ label, value, sub, highlight }) => (
          <div
            key={label}
            className="rounded-xl p-4"
            style={{
              background: 'var(--color-bg-surface)',
              border: '1px solid var(--color-border)',
            }}
          >
            <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              {label}
            </p>
            <p
              className="mt-1 text-[20px] font-bold tabular-nums"
              style={{ color: highlight ?? 'var(--color-text-primary)' }}
            >
              {value}
            </p>
            {sub && <p className="mt-0.5 text-[10px]" style={{ color: 'var(--color-text-muted)' }}>{sub}</p>}
          </div>
        ))}
      </div>

      {/* Items table */}
      <div
        className="overflow-hidden rounded-xl"
        style={{
          background: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--color-border)' }}>
          <p className="text-[12px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            İşlenen Ürünler ({items.length})
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Ürün Adı', 'Skor Değişimi', 'Durum', 'Gerekçe', 'Eylem'].map((col) => (
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
              {items.map((item) => {
                const sc = ITEM_STATUS_COLORS[item.status] ?? ITEM_STATUS_COLORS.pending;
                return (
                  <tr
                    key={item.id}
                    style={{ borderBottom: '1px solid var(--color-border)' }}
                  >
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
                            border: '1px solid rgba(239,68,68,0.25)',
                            color: '#ef4444',
                          }}
                        >
                          Önceki Sürüme Dön
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Per-item rollback confirm */}
      <ConfirmDialog
        open={rollbackItemId !== null}
        title="Önceki Sürüme Dön"
        message="Bu ürün için yapılan değişiklikler geri alınacak ve orijinal içerik ikas'a geri yüklenecektir. Devam etmek istiyor musunuz?"
        confirmLabel="Geri Al"
        cancelLabel="İptal"
        variant="danger"
        onConfirm={() => {
          if (rollbackItemId !== null) onRollbackItem(rollbackItemId);
          setRollbackItemId(null);
        }}
        onCancel={() => setRollbackItemId(null)}
      />

      {/* Full job rollback confirm */}
      <ConfirmDialog
        open={showRollbackAll}
        title="Tüm İşlemi Geri Al"
        message={`Bu işteki ${appliedCount} ürün için yapılan tüm değişiklikler geri alınacak. Bu işlem geri alınamaz. Devam etmek istiyor musunuz?`}
        confirmLabel="Tüm Değişiklikleri Geri Al"
        cancelLabel="İptal"
        variant="danger"
        onConfirm={() => { setShowRollbackAll(false); onRollbackAll(); }}
        onCancel={() => setShowRollbackAll(false)}
      />
    </div>
  );
}

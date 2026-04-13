import { useState } from 'react';
import type { BatchItem, BatchJob } from '../../types';
import ProgressBar from '../../shared/ui/ProgressBar';
import ConfirmDialog from '../../shared/ui/ConfirmDialog';

interface Props {
  job: BatchJob;
  items: BatchItem[];
  onDecision: (itemId: number, decision: 'approved' | 'rejected' | 'revised') => void;
  onConfirmRun: () => void;
  isMutating: boolean;
}

function ScoreBadge({ before, after }: { before: number | null; after: number | null }) {
  if (before === null) return null;
  const delta = after !== null ? after - before : null;
  return (
    <div className="flex items-center gap-2 text-[12px]">
      <span className="tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
        {before}
      </span>
      {after !== null && (
        <>
          <span style={{ color: 'var(--color-text-muted)' }}>→</span>
          <span className="font-semibold tabular-nums" style={{ color: 'var(--color-text-primary)' }}>
            {after}
          </span>
          {delta !== null && (
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-bold"
              style={{
                background: delta > 0 ? 'var(--tint-success-soft)' : delta < 0 ? 'var(--tint-danger-soft)' : 'var(--color-border-subtle)',
                color: delta > 0 ? 'var(--color-success)' : delta < 0 ? 'var(--color-danger)' : 'var(--color-text-secondary)',
              }}
            >
              {delta > 0 ? '+' : ''}{delta}
            </span>
          )}
        </>
      )}
    </div>
  );
}

function DiffRow({ label, before, after }: { label: string; before: string; after: string }) {
  const changed = before !== after && after;
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <p className="mb-0.5 text-[10px] uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
          {label} — Mevcut
        </p>
        <p
          className="rounded-lg px-2.5 py-2 text-[12px] leading-relaxed"
          style={{
            background: 'var(--alpha-white-3)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)',
            maxHeight: '80px',
            overflow: 'hidden',
          }}
        >
          {before || <em style={{ opacity: 0.4 }}>Boş</em>}
        </p>
      </div>
      <div>
        <p className="mb-0.5 text-[10px] uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
          {label} — Önerilen
        </p>
        <p
          className="rounded-lg px-2.5 py-2 text-[12px] leading-relaxed"
          style={{
            background: changed ? 'var(--tint-primary-bg)' : 'var(--alpha-white-3)',
            border: changed ? '1px solid var(--color-border-primary)' : '1px solid var(--color-border)',
            color: changed ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
            maxHeight: '80px',
            overflow: 'hidden',
          }}
        >
          {after || <em style={{ opacity: 0.4 }}>Değişiklik yok</em>}
        </p>
      </div>
    </div>
  );
}

function ItemCard({
  item,
  onDecision,
  calibrationDone,
}: {
  item: BatchItem;
  onDecision: (id: number, decision: 'approved' | 'rejected' | 'revised') => void;
  calibrationDone: boolean;
}) {
  const [decided, setDecided] = useState<'approved' | 'rejected' | null>(null);

  const isApproved = decided === 'approved' || item.status === 'approved';
  const isRejected = decided === 'rejected' || item.status === 'rejected';
  const isProcessing = !item.suggestion_data && item.status !== 'failed' && item.status !== 'skipped' && !calibrationDone;
  const noSuggestion = !item.suggestion_data && calibrationDone && item.status !== 'failed' && item.status !== 'skipped';

  const decide = (d: 'approved' | 'rejected') => {
    setDecided(d);
    onDecision(item.id, d);
  };

  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: isApproved
          ? 'var(--tint-success-bg)'
          : isRejected
          ? 'var(--tint-danger-bg)'
          : 'var(--color-bg-surface)',
        border: isApproved
          ? '1px solid var(--color-border-success)'
          : isRejected
          ? '1px solid var(--color-border-danger)'
          : '1px solid var(--color-border)',
        opacity: isRejected ? 0.65 : 1,
      }}
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-[14px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {item.product_name}
          </p>
          <ScoreBadge before={item.score_before} after={item.score_after} />
        </div>
        {isProcessing && (
          <span
            className="flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold"
            style={{ background: 'var(--tint-primary-soft)', color: 'var(--color-primary-light)' }}
          >
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
            AI İşliyor...
          </span>
        )}
        {!isProcessing && !isApproved && !isRejected && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => decide('approved')}
              className="rounded-lg px-3 py-1.5 text-[12px] font-semibold text-white transition-opacity hover:opacity-90"
              style={{ background: 'linear-gradient(135deg, var(--color-success), var(--color-success))' }}
            >
              Taslağı Onayla
            </button>
            <button
              type="button"
              onClick={() => decide('rejected')}
              className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors hover:bg-[var(--color-bg-hover)]"
              style={{
                border: '1px solid var(--color-border-danger)',
                color: 'var(--color-danger)',
              }}
            >
              Reddet
            </button>
          </div>
        )}
        {isApproved && (
          <span
            className="rounded-full px-3 py-1 text-[11px] font-semibold"
            style={{ background: 'var(--tint-success-soft)', color: 'var(--color-success)' }}
          >
            Onaylandı
          </span>
        )}
        {isRejected && (
          <span
            className="rounded-full px-3 py-1 text-[11px] font-semibold"
            style={{ background: 'var(--tint-danger-soft)', color: 'var(--color-danger)' }}
          >
            Reddedildi
          </span>
        )}
      </div>

      {/* Diff rows — only show when not rejected and has data */}
      {!isRejected && !isProcessing && item.status !== 'failed' && item.status !== 'skipped' && (
        <div className="space-y-2.5">
          <DiffRow
            label="Başlık"
            before={String(item.suggestion_data?.original_name ?? '')}
            after={String(item.suggestion_data?.suggested_name ?? '')}
          />
          <DiffRow
            label="Meta Başlık"
            before={String(item.suggestion_data?.original_meta_title ?? '')}
            after={String(item.suggestion_data?.suggested_meta_title ?? '')}
          />
          <DiffRow
            label="Meta Açıklama"
            before={String(item.suggestion_data?.original_meta_description ?? '')}
            after={String(item.suggestion_data?.suggested_meta_description ?? '')}
          />
          {(String(item.suggestion_data?.original_description ?? '') || String(item.suggestion_data?.suggested_description ?? '')) && (
            <DiffRow
              label="Açıklama"
              before={String(item.suggestion_data?.original_description ?? '')}
              after={String(item.suggestion_data?.suggested_description ?? '')}
            />
          )}
        </div>
      )}

      {/* Loading indicator while AI processes */}
      {isProcessing && (
        <div
          className="mt-2 flex items-center gap-2 rounded-lg px-4 py-3"
          style={{
            background: 'var(--tint-primary-bg)',
            border: '1px solid var(--tint-primary-soft)',
          }}
        >
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
          <p className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            AI bu ürün için SEO önerisi oluşturuyor...
          </p>
        </div>
      )}

      {/* No suggestion generated after calibration finished */}
      {noSuggestion && (
        <p className="mt-2 rounded-lg px-3 py-2 text-[12px]" style={{
          background: 'rgba(100,116,139,0.08)',
          border: '1px solid var(--color-border-subtle)',
          color: 'var(--color-text-secondary)',
        }}>
          AI bu ürün için öneri oluşturamadı.
        </p>
      )}

      {(item.status === 'failed' || item.status === 'skipped') && (
        <p className="mt-2 rounded-lg px-3 py-2 text-[12px]" style={{
          background: 'var(--tint-danger-bg)',
          border: '1px solid var(--tint-danger-soft)',
          color: 'var(--color-danger)',
        }}>
          {item.skip_reason || 'İşlem başarısız'}
        </p>
      )}
    </div>
  );
}

export default function CalibrationReview({ job, items, onDecision, onConfirmRun, isMutating }: Props) {
  const [showConfirm, setShowConfirm] = useState(false);

  const approvedCount = items.filter((i) => i.status === 'approved').length;
  const totalItems = items.length;
  const confidencePct = totalItems > 0 ? Math.round((approvedCount / totalItems) * 100) : 0;
  const canConfirm = approvedCount >= Math.ceil(totalItems * 0.5);
  const remaining = job.total_count - totalItems;
  const calibrationDone = job.status === 'analyzed' || job.processed_count >= job.total_count;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div
        className="rounded-xl p-5"
        style={{
          background: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-[16px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
              Kalibrasyon — {totalItems} Örneklem İncelemesi
            </h2>
            <p className="mt-0.5 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              Her taslağı inceleyin. Çoğunluğu onaylayarak sistemi kalibre edin.
            </p>
          </div>
          <div className="text-right">
            <p className="text-[24px] font-bold tabular-nums" style={{
              color: confidencePct >= 70 ? 'var(--color-success)' : confidencePct >= 50 ? 'var(--color-warning)' : 'var(--color-danger)',
            }}>
              %{confidencePct}
            </p>
            <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              Güven Skoru ({approvedCount}/{totalItems})
            </p>
          </div>
        </div>
        <ProgressBar pct={confidencePct} animated height="h-2" />
      </div>

      {/* Item cards */}
      <div className="space-y-3">
        {items.map((item) => (
          <ItemCard
            key={item.id}
            item={item}
            onDecision={onDecision}
            calibrationDone={calibrationDone}
          />
        ))}
      </div>

      {/* CTA footer */}
      <div
        className="sticky bottom-0 rounded-xl p-4"
        style={{
          background: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              {canConfirm
                ? `Kalibrasyon tamamlandı. Kalan ${remaining} ürün işlenecektir.`
                : `En az ${Math.ceil(totalItems * 0.5)} taslağı onaylamanız gerekiyor.`}
            </p>
            <p className="mt-0.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {approvedCount} onaylandı · {totalItems - approvedCount} bekliyor
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowConfirm(true)}
            disabled={!canConfirm || isMutating}
            className="rounded-lg px-5 py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-primary))' }}
          >
            {isMutating ? 'Başlatılıyor...' : 'Toplu İşlemi Başlat'}
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={showConfirm}
        title="Toplu İşlemi Başlat"
        message={`Kalibrasyon onaylandı (%${confidencePct} güven skoru). Kalan ${remaining} ürün arka planda işlenecektir. Devam etmek istiyor musunuz?`}
        confirmLabel="Başlat"
        cancelLabel="İptal"
        onConfirm={() => { setShowConfirm(false); onConfirmRun(); }}
        onCancel={() => setShowConfirm(false)}
      />
    </div>
  );
}

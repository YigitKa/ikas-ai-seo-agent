import type { BatchJob, BatchItem } from '../../types';

interface Props {
  job: BatchJob;
  items: BatchItem[];
  onDecision: (itemId: number, decision: 'approved' | 'rejected') => void;
  onBulkDecision?: (itemIds: number[], decision: 'approved' | 'rejected') => void;
  onApplyAll: () => void;
  onStop?: () => void;
  onBack?: () => void;
  isMutating: boolean;
}

const DIFF_FIELDS: { key: string; label: string }[] = [
  { key: 'name', label: 'Başlık' },
  { key: 'meta_title', label: 'Meta Başlık' },
  { key: 'meta_description', label: 'Meta Açıklama' },
  { key: 'description', label: 'Açıklama' },
];

function DiffRow({ label, original, suggested }: { label: string; original: string; suggested: string }) {
  const changed = original !== suggested && suggested !== '';
  return (
    <div
      className="grid grid-cols-[100px_1fr_1fr] gap-2 rounded-lg px-3 py-2"
      style={{ background: 'var(--color-bg-primary)' }}
    >
      <span className="text-[11px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
        {label}
      </span>
      <p
        className="text-[12px] leading-relaxed"
        style={{ color: 'var(--color-text-secondary)', maxHeight: 80, overflow: 'hidden' }}
      >
        {original || <span style={{ opacity: 0.4 }}>Boş</span>}
      </p>
      <p
        className="text-[12px] leading-relaxed"
        style={{
          color: changed ? '#22c55e' : 'var(--color-text-secondary)',
          maxHeight: 80,
          overflow: 'hidden',
        }}
      >
        {suggested || <span style={{ opacity: 0.4 }}>Değişiklik yok</span>}
      </p>
    </div>
  );
}

function ScoreBadge({ before, after }: { before: number | null; after: number | null }) {
  if (before == null || after == null) return null;
  const delta = after - before;
  const color = delta > 0 ? '#22c55e' : delta < 0 ? '#ef4444' : '#94a3b8';
  return (
    <span
      className="rounded-full px-2 py-0.5 text-[11px] font-bold"
      style={{ background: `${color}18`, color }}
    >
      {before} → {after} ({delta > 0 ? '+' : ''}{delta})
    </span>
  );
}

function ItemCard({
  item,
  analysisComplete,
  onDecision,
}: {
  item: BatchItem;
  analysisComplete: boolean;
  onDecision: (decision: 'approved' | 'rejected') => void;
}) {
  const sd = item.suggestion_data;
  const isProcessing = item.status === 'pending' && !analysisComplete;
  const noSuggestion = !sd && analysisComplete && item.status !== 'failed' && item.status !== 'skipped';

  return (
    <div
      className="rounded-xl p-4"
      style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {item.product_name}
          </p>
          <ScoreBadge before={item.score_before} after={item.score_after} />
        </div>
        <div className="flex items-center gap-2">
          {item.status === 'approved' && (
            <button
              onClick={() => onDecision('rejected')}
              className="rounded-full px-2 py-0.5 text-[11px] font-medium transition hover:opacity-70"
              style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e' }}
              title="Kararı değiştir"
            >
              ✓ Onaylandı
            </button>
          )}
          {item.status === 'rejected' && (
            <button
              onClick={() => onDecision('approved')}
              className="rounded-full px-2 py-0.5 text-[11px] font-medium transition hover:opacity-70"
              style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}
              title="Kararı değiştir"
            >
              ✕ Reddedildi
            </button>
          )}
          {(item.status === 'analyzed' || item.status === 'pending') && sd && (
            <>
              <button
                onClick={() => onDecision('approved')}
                className="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white transition hover:opacity-80"
                style={{ background: '#22c55e' }}
              >
                Onayla
              </button>
              <button
                onClick={() => onDecision('rejected')}
                className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition hover:opacity-80"
                style={{
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  color: '#ef4444',
                }}
              >
                Reddet
              </button>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      {isProcessing && (
        <div className="flex items-center gap-2 py-4">
          <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="#6366f1" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            AI analiz ediyor...
          </span>
        </div>
      )}

      {noSuggestion && (
        <p className="py-3 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
          AI bu ürün için öneri oluşturamadı.
        </p>
      )}

      {item.status === 'failed' && (
        <p className="py-3 text-[12px]" style={{ color: '#ef4444' }}>
          Hata: {item.skip_reason || 'Bilinmeyen hata'}
        </p>
      )}

      {item.status === 'skipped' && (
        <p className="py-3 text-[12px]" style={{ color: '#f59e0b' }}>
          Atlandı: {item.skip_reason || 'AI bu ürün için öneri oluşturamadı.'}
        </p>
      )}

      {sd && (
        <div className="space-y-1">
          {/* Column headers */}
          <div className="grid grid-cols-[100px_1fr_1fr] gap-2 px-3">
            <span />
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Mevcut
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Önerilen
            </span>
          </div>
          {DIFF_FIELDS.map(f => (
            <DiffRow
              key={f.key}
              label={f.label}
              original={sd[`original_${f.key}`] ?? ''}
              suggested={sd[`suggested_${f.key}`] ?? ''}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function AnalysisReview({
  job,
  items,
  onDecision,
  onBulkDecision,
  onApplyAll,
  onStop,
  onBack,
  isMutating,
}: Props) {
  const analysisComplete = job.status === 'analyzed';
  const visibleItems = items.filter(i => i.status !== 'applied' && i.status !== 'rolled_back');

  const approvedCount = items.filter(i => i.status === 'approved').length;
  const rejectedCount = items.filter(i => i.status === 'rejected').length;
  const pendingDecision = items.filter(i =>
    (i.status === 'analyzed' || i.status === 'pending') && i.suggestion_data != null
  ).length;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div
        className="flex items-center justify-between rounded-xl px-5 py-3"
        style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center gap-4">
          <span className="text-[13px]" style={{ color: 'var(--color-text-secondary)' }}>
            {analysisComplete ? 'Analiz tamamlandı' : `Analiz ediliyor... (${job.processed_count}/${job.total_count})`}
          </span>
          <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            {approvedCount} onaylandı · {pendingDecision} bekliyor
            {rejectedCount > 0 && ` · ${rejectedCount} reddedildi`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Stop analysis */}
          {!analysisComplete && onStop && (
            <button
              onClick={onStop}
              className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition hover:opacity-80"
              style={{
                background: 'rgba(239,68,68,0.1)',
                border: '1px solid rgba(239,68,68,0.3)',
                color: '#ef4444',
              }}
            >
              Analizi Durdur
            </button>
          )}
          {/* Approve all pending */}
          {pendingDecision > 0 && (
            <button
              onClick={() => {
                const ids = items
                  .filter(i => (i.status === 'analyzed' || i.status === 'pending') && i.suggestion_data)
                  .map(i => i.id);
                if (onBulkDecision && ids.length > 1) {
                  onBulkDecision(ids, 'approved');
                } else {
                  ids.forEach(id => onDecision(id, 'approved'));
                }
              }}
              className="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white transition hover:opacity-80"
              style={{ background: '#22c55e' }}
            >
              Tümünü Onayla
            </button>
          )}
          {/* Apply */}
          {analysisComplete && approvedCount > 0 && (
            <button
              disabled={isMutating}
              onClick={onApplyAll}
              className="rounded-lg px-4 py-1.5 text-[12px] font-semibold text-white transition hover:opacity-80 disabled:opacity-40"
              style={{ background: '#6366f1' }}
            >
              {isMutating ? 'Uygulanıyor...' : `${approvedCount} Ürünü Uygula`}
            </button>
          )}
        </div>
      </div>

      {/* Progress bar while analyzing */}
      {!analysisComplete && job.total_count > 0 && (
        <div className="h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--color-border)' }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${(job.processed_count / job.total_count) * 100}%`,
              background: '#6366f1',
            }}
          />
        </div>
      )}

      {/* Item cards */}
      <div className="space-y-3">
        {visibleItems.map(item => (
          <ItemCard
            key={item.id}
            item={item}
            analysisComplete={analysisComplete}
            onDecision={(decision) => onDecision(item.id, decision)}
          />
        ))}
      </div>

      {/* Empty-state: analysis done but nothing actionable */}
      {analysisComplete && pendingDecision === 0 && approvedCount === 0 && onBack && (
        <div
          className="rounded-xl p-6 text-center"
          style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
        >
          <p className="text-[13px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Onaylanacak öneri bulunamadı.
          </p>
          <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            AI bu ürünler için öneri oluşturamadı veya tüm öneriler reddedildi.
            Farklı ürünler seçerek tekrar deneyebilirsiniz.
          </p>
          <button
            onClick={onBack}
            className="mt-4 rounded-lg px-4 py-2 text-[13px] font-medium text-white transition hover:opacity-80"
            style={{ background: '#6366f1' }}
          >
            Ürün Seçimine Dön
          </button>
        </div>
      )}
    </div>
  );
}

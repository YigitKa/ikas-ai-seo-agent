import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import type { BatchConfig, BatchItem } from '../types';
import type { QueryClient } from '@tanstack/react-query';
import {
  getBatchStats,
  listBatchJobs,
  getBatchJob,
  startBatchJob,
  applyBatchJob,
  stopBatchJob,
  rollbackBatchJob,
  rollbackBatchItem,
  regenerateBatchItem,
  regenerateBatchItemField,
  updateBatchItem,
  bulkUpdateBatchItems,
  deleteBatchJob,
} from '../api/client';
import { useToast } from '../shared/ui/Toast';
import ProductSelector from '../components/batch/ProductSelector';
import AnalysisReview from '../components/batch/AnalysisReview';
import BatchProgressView from '../components/batch/BatchProgressView';
import BatchJobDetail from '../components/batch/BatchJobDetail';
import BatchHistory from '../components/batch/BatchHistory';

type View = 'select' | 'analyzing' | 'review' | 'running' | 'detail';

function invalidateBatch(qc: QueryClient, jobId?: string | null) {
  qc.invalidateQueries({ queryKey: ['batchJobs'] });
  qc.invalidateQueries({ queryKey: ['batchStats'] });
  if (jobId) qc.invalidateQueries({ queryKey: ['batchJob', jobId] });
}

const DEFAULT_CONFIG: BatchConfig = {
  score_threshold: 70,
  category_filter: '',
  in_stock_only: false,
  preserve_specs: true,
  prevent_cannibalization: true,
  max_title_change_pct: 40,
  target_fields: ['name', 'description', 'meta_title', 'meta_description'],
};

export default function BatchOperations() {
  const qc = useQueryClient();
  const { addToast } = useToast();

  const [view, setView] = useState<View>('select');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [config, setConfig] = useState<BatchConfig>(DEFAULT_CONFIG);
  const [regeneratingKey, setRegeneratingKey] = useState<string | null>(null);

  // ── Queries ────────────────────────────────────────────────────────────────

  const { data: stats } = useQuery({
    queryKey: ['batchStats'],
    queryFn: getBatchStats,
    refetchInterval: view === 'running' || view === 'analyzing' ? 3000 : 10000,
  });

  const { data: jobs = [] } = useQuery({
    queryKey: ['batchJobs'],
    queryFn: listBatchJobs,
    refetchInterval: 15000,
  });

  const { data: activeDetail } = useQuery({
    queryKey: ['batchJob', activeJobId],
    queryFn: () => getBatchJob(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: view === 'analyzing' || view === 'running' ? 4000 : false,
  });

  const activeJob = activeDetail?.job ?? null;
  const activeItems: BatchItem[] = activeDetail?.items ?? [];

  // Sync view with job status when polling updates come in
  const prevStatusRef = useRef<string | null>(null);
  useEffect(() => {
    if (!activeJob) return;
    const st = activeJob.status;
    if (st === prevStatusRef.current) return;
    prevStatusRef.current = st;
    if (st === 'analyzing') setView('analyzing');
    else if (st === 'analyzed') setView('review');
    else if (st === 'running') setView('running');
    else if (st === 'completed' || st === 'failed' || st === 'cancelled') setView('detail');
  }, [activeJob?.status]);

  // ── Mutations ──────────────────────────────────────────────────────────────

  const startMutation = useMutation({
    mutationFn: (productIds: string[]) => startBatchJob(config, productIds),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      setView('analyzing');
      prevStatusRef.current = job.status;
      invalidateBatch(qc);
      addToast({ tone: 'success', message: 'Analiz başlatıldı.' });
    },
    onError: (err: Error) => addToast({ tone: 'error', message: err.message }),
  });

  const applyMutation = useMutation({
    mutationFn: () => applyBatchJob(activeJobId!),
    onSuccess: () => {
      setView('running');
      prevStatusRef.current = 'running';
      invalidateBatch(qc, activeJobId);
      addToast({ tone: 'success', message: 'Uygulama başlatıldı.' });
    },
    onError: (err: Error) => addToast({ tone: 'error', message: err.message }),
  });

  const stopMutation = useMutation({
    mutationFn: () => stopBatchJob(activeJobId!),
    onSuccess: () => {
      invalidateBatch(qc, activeJobId);
      addToast({ tone: 'info', message: 'İşlem durduruldu.' });
    },
  });

  const rollbackItemMutation = useMutation({
    mutationFn: (itemId: number) => rollbackBatchItem(itemId),
    onSuccess: () => {
      invalidateBatch(qc, activeJobId);
      addToast({ tone: 'success', message: 'Ürün önceki sürüme döndürüldü.' });
    },
    onError: (err: Error) => addToast({ tone: 'error', message: err.message }),
  });

  const rollbackAllMutation = useMutation({
    mutationFn: () => rollbackBatchJob(activeJobId!),
    onSuccess: (res) => {
      invalidateBatch(qc, activeJobId);
      addToast({ tone: 'success', message: `${res.rolled_back} ürün geri alındı.` });
    },
    onError: (err: Error) => addToast({ tone: 'error', message: err.message }),
  });

  const decisionMutation = useMutation({
    mutationFn: ({
      itemId,
      decision,
      revisedData,
    }: {
      itemId: number;
      decision: 'approved' | 'rejected' | 'revised';
      revisedData?: Record<string, string>;
    }) => updateBatchItem(itemId, decision, revisedData),
    onSuccess: () => invalidateBatch(qc, activeJobId),
  });

  const bulkDecisionMutation = useMutation({
    mutationFn: ({ itemIds, decision }: { itemIds: number[]; decision: 'approved' | 'rejected' }) =>
      bulkUpdateBatchItems(itemIds, decision),
    onSuccess: () => invalidateBatch(qc, activeJobId),
  });

  const regenerateMutation = useMutation({
    mutationFn: (itemId: number) => regenerateBatchItem(itemId),
    onMutate: (itemId) => {
      setRegeneratingKey(`item:${itemId}`);
    },
    onSuccess: (item) => {
      invalidateBatch(qc, activeJobId);
      const succeeded = item.status === 'analyzed';
      addToast({
        tone: succeeded ? 'success' : 'error',
        message: succeeded
          ? 'Öneri yeniden üretildi.'
          : item.skip_reason || 'Öneri yeniden üretilemedi.',
      });
    },
    onError: (err: Error) => {
      addToast({ tone: 'error', message: err.message });
    },
    onSettled: () => {
      setRegeneratingKey(null);
    },
  });

  const regenerateFieldMutation = useMutation({
    mutationFn: ({ itemId, fieldKey }: { itemId: number; fieldKey: string }) =>
      regenerateBatchItemField(itemId, fieldKey),
    onMutate: ({ itemId, fieldKey }) => {
      setRegeneratingKey(`${itemId}:${fieldKey}`);
    },
    onSuccess: (item, variables) => {
      invalidateBatch(qc, activeJobId);
      const fieldLabels: Record<string, string> = {
        name: 'Başlık',
        meta_title: 'Meta Başlık',
        meta_description: 'Meta Açıklama',
        description: 'Açıklama',
        description_en: 'Açıklama (EN)',
      };
      addToast({
        tone: item.status === 'failed' ? 'error' : 'success',
        message: `${fieldLabels[variables.fieldKey] ?? variables.fieldKey} alanı yeniden üretildi.`,
      });
    },
    onError: (err: Error) => {
      addToast({ tone: 'error', message: err.message });
    },
    onSettled: () => {
      setRegeneratingKey(null);
    },
  });

  const deleteJobMutation = useMutation({
    mutationFn: (jobId: string) => deleteBatchJob(jobId),
    onSuccess: () => {
      invalidateBatch(qc);
      addToast({ tone: 'success', message: 'İş silindi.' });
    },
    onError: (err: Error) => addToast({ tone: 'error', message: err.message }),
  });

  // ── Helpers ────────────────────────────────────────────────────────────────

  const defaultStats = stats ?? { total_jobs: 0, total_processed: 0, avg_score_improvement: 0, active_job: null };

  const handleJobComplete = useCallback((jobId: string) => {
    invalidateBatch(qc, jobId);
    setView('detail');
  }, [qc]);

  const handleBackToSelect = useCallback(() => {
    setView('select');
    setActiveJobId(null);
    prevStatusRef.current = null;
  }, []);

  const isReviewViewport = view === 'analyzing' || view === 'review';

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
      {/* Page header */}
      <header
        className="flex flex-shrink-0 items-center justify-between px-6 py-3"
        style={{
          background: 'var(--color-bg-surface)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-1.5 text-[13px] transition-opacity hover:opacity-70"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Dashboard
          </Link>
          <span style={{ color: 'var(--color-border)' }}>/</span>
          <h1 className="text-[15px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Otonom SEO Yöneticisi
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {view !== 'select' && (
            <button
              type="button"
              onClick={handleBackToSelect}
              className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors hover:bg-[var(--color-bg-hover)]"
              style={{
                border: '1px solid var(--color-border-light)',
                color: 'var(--color-text-secondary)',
              }}
            >
              Ürün Seçimi
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto px-4 py-4 lg:px-6">
        <div className={`mx-auto ${isReviewViewport ? 'max-w-[1560px]' : 'max-w-6xl'}`}>

          {/* PRODUCT SELECTION */}
          {view === 'select' && (
            <div className="space-y-6">
              {/* Stats summary */}
              {defaultStats.total_jobs > 0 && (
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: 'Toplam İş', value: defaultStats.total_jobs },
                    { label: 'İşlenen Ürün', value: defaultStats.total_processed },
                    { label: 'Ort. Skor Artışı', value: `+${defaultStats.avg_score_improvement.toFixed(1)}`, color: '#22c55e' },
                  ].map(({ label, value, color }) => (
                    <div
                      key={label}
                      className="rounded-xl p-4"
                      style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
                    >
                      <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                        {label}
                      </p>
                      <p className="mt-1 text-[20px] font-bold tabular-nums" style={{ color: color ?? 'var(--color-text-primary)' }}>
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Active job banner */}
              {defaultStats.active_job && (
                <div
                  className="flex items-center justify-between rounded-xl px-5 py-3"
                  style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.25)' }}
                >
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 animate-pulse rounded-full" style={{ background: '#6366f1' }} />
                    <span className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      Aktif bir iş çalışıyor
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const aj = defaultStats.active_job!;
                      setActiveJobId(aj.id);
                      const st = aj.status;
                      if (st === 'analyzed') setView('review');
                      else if (st === 'running') setView('running');
                      else if (st === 'completed' || st === 'failed' || st === 'cancelled') setView('detail');
                      else setView('analyzing');
                    }}
                    className="rounded-lg px-3 py-1 text-[12px] font-medium"
                    style={{ color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)' }}
                  >
                    Görüntüle
                  </button>
                </div>
              )}

              <ProductSelector
                config={config}
                onChange={setConfig}
                onStartAnalysis={(productIds) => startMutation.mutate(productIds)}
                disabled={startMutation.isPending}
              />

              {/* Job history */}
              {jobs.length > 0 && (
                <BatchHistory
                  jobs={jobs}
                  onSelect={(jobId, status) => {
                    setActiveJobId(jobId);
                    if (status === 'analyzing') setView('analyzing');
                    else if (status === 'analyzed') setView('review');
                    else if (status === 'running') setView('running');
                    else setView('detail');
                  }}
                  onDelete={(jobId) => deleteJobMutation.mutate(jobId)}
                />
              )}
            </div>
          )}

          {/* ANALYZING / REVIEW — shared AnalysisReview for both phases */}
          {(view === 'analyzing' || view === 'review') && activeJob && (
            <AnalysisReview
              job={activeJob}
              items={activeItems}
              onDecision={(itemId, decision, revisedData) => decisionMutation.mutate({ itemId, decision, revisedData })}
              onRegenerate={(itemId) => regenerateMutation.mutate(itemId)}
              onFieldRegenerate={(itemId, fieldKey) => regenerateFieldMutation.mutate({ itemId, fieldKey })}
              onBulkDecision={(itemIds, decision) => bulkDecisionMutation.mutate({ itemIds, decision })}
              onApplyAll={() => applyMutation.mutate()}
              onStop={() => stopMutation.mutate()}
              onBack={handleBackToSelect}
              isMutating={
                applyMutation.isPending
                || decisionMutation.isPending
                || bulkDecisionMutation.isPending
                || regeneratingKey !== null
              }
              regeneratingKey={regeneratingKey}
            />
          )}

          {/* RUNNING — applying approved items */}
          {view === 'running' && activeJob && (
            <BatchProgressView
              job={activeJob}
              onStop={() => stopMutation.mutate()}
              onJobComplete={handleJobComplete}
            />
          )}

          {/* JOB DETAIL — history + rollback */}
          {view === 'detail' && activeJob && (
            <BatchJobDetail
              job={activeJob}
              items={activeItems}
              onRollbackItem={(itemId) => rollbackItemMutation.mutate(itemId)}
              onRollbackAll={() => rollbackAllMutation.mutate()}
              onBack={handleBackToSelect}
              isRollingBack={rollbackItemMutation.isPending || rollbackAllMutation.isPending}
            />
          )}

          {/* Loading state when job ID is set but detail not yet loaded */}
          {(view === 'analyzing' || view === 'review' || view === 'detail') && activeJobId && !activeJob && (
            <div className="flex items-center justify-center py-20">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

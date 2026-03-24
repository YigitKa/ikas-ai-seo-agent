import { useCallback, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import type { BatchConfig, BatchJob, BatchItem } from '../types';
import {
  getBatchStats,
  listBatchJobs,
  getBatchJob,
  startBatchJob,
  startFullBatchRun,
  stopBatchJob,
  rollbackBatchJob,
  rollbackBatchItem,
  updateBatchItem,
} from '../api/client';
import { useToast } from '../shared/ui/Toast';
import BatchCommandCenter from '../components/batch/BatchCommandCenter';
import CalibrationReview from '../components/batch/CalibrationReview';
import BatchProgressView from '../components/batch/BatchProgressView';
import BatchJobDetail from '../components/batch/BatchJobDetail';

type View = 'command' | 'calibrating' | 'running' | 'detail';

export default function BatchOperations() {
  const qc = useQueryClient();
  const { addToast } = useToast();

  const [view, setView] = useState<View>('command');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  // ── Queries ────────────────────────────────────────────────────────────────

  const { data: stats } = useQuery({
    queryKey: ['batchStats'],
    queryFn: getBatchStats,
    refetchInterval: view === 'running' ? 3000 : 10000,
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
    refetchInterval: view === 'calibrating' || view === 'running' ? 4000 : false,
  });

  const activeJob = activeDetail?.job ?? null;
  const activeItems: BatchItem[] = activeDetail?.items ?? [];

  // Sync view with job status when polling updates come in
  const syncView = useCallback((job: BatchJob) => {
    if (job.status === 'calibrating') setView('calibrating');
    else if (job.status === 'running') setView('running');
    else if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') setView('detail');
  }, []);

  if (activeJob) {
    syncView(activeJob);
  }

  // ── Mutations ──────────────────────────────────────────────────────────────

  const startMutation = useMutation({
    mutationFn: ({ config, calibrate }: { config: BatchConfig; calibrate: boolean }) =>
      startBatchJob(config, calibrate),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      setView(job.status === 'calibrating' ? 'calibrating' : 'running');
      qc.invalidateQueries({ queryKey: ['batchJobs'] });
      qc.invalidateQueries({ queryKey: ['batchStats'] });
      addToast({ tone: 'success', message: 'Toplu işlem başlatıldı.' });
    },
    onError: (err: Error) => {
      addToast({ tone: 'error', message: err.message });
    },
  });

  const confirmRunMutation = useMutation({
    mutationFn: () => startFullBatchRun(activeJobId!),
    onSuccess: () => {
      setView('running');
      qc.invalidateQueries({ queryKey: ['batchJob', activeJobId] });
      addToast({ tone: 'success', message: 'Toplu optimizasyon başlatıldı.' });
    },
    onError: (err: Error) => {
      addToast({ tone: 'error', message: err.message });
    },
  });

  const stopMutation = useMutation({
    mutationFn: () => stopBatchJob(activeJobId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['batchJob', activeJobId] });
      qc.invalidateQueries({ queryKey: ['batchStats'] });
      addToast({ tone: 'info', message: 'İşlem durduruldu.' });
    },
  });

  const rollbackItemMutation = useMutation({
    mutationFn: (itemId: number) => rollbackBatchItem(itemId),
    onSuccess: (_, itemId) => {
      qc.invalidateQueries({ queryKey: ['batchJob', activeJobId] });
      addToast({ tone: 'success', message: 'Ürün önceki sürüme döndürüldü.' });
    },
    onError: (err: Error) => {
      addToast({ tone: 'error', message: err.message });
    },
  });

  const rollbackAllMutation = useMutation({
    mutationFn: () => rollbackBatchJob(activeJobId!),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['batchJob', activeJobId] });
      addToast({ tone: 'success', message: `${res.rolled_back} ürün geri alındı.` });
    },
    onError: (err: Error) => {
      addToast({ tone: 'error', message: err.message });
    },
  });

  const decisionMutation = useMutation({
    mutationFn: ({ itemId, decision }: { itemId: number; decision: 'approved' | 'rejected' | 'revised' }) =>
      updateBatchItem(itemId, decision),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['batchJob', activeJobId] });
    },
  });

  // ── Helpers ────────────────────────────────────────────────────────────────

  const defaultStats = stats ?? { total_jobs: 0, total_processed: 0, avg_score_improvement: 0, active_job: null };
  const isDisabled = view !== 'command' || startMutation.isPending;

  const handleJobComplete = useCallback((jobId: string) => {
    qc.invalidateQueries({ queryKey: ['batchJob', jobId] });
    qc.invalidateQueries({ queryKey: ['batchJobs'] });
    qc.invalidateQueries({ queryKey: ['batchStats'] });
    setView('detail');
  }, [qc]);

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
          {view !== 'command' && (
            <button
              type="button"
              onClick={() => { setView('command'); setActiveJobId(null); }}
              className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors hover:bg-[var(--color-bg-hover)]"
              style={{
                border: '1px solid var(--color-border-light)',
                color: 'var(--color-text-secondary)',
              }}
            >
              Kontrol Paneli
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto px-6 py-5">
        <div className="mx-auto max-w-6xl">

          {/* COMMAND CENTER */}
          {view === 'command' && (
            <BatchCommandCenter
              stats={defaultStats}
              jobs={jobs}
              onStartCalibration={(config) => startMutation.mutate({ config, calibrate: true })}
              onStartDirect={(config) => startMutation.mutate({ config, calibrate: false })}
              onViewJob={(jobId) => { setActiveJobId(jobId); setView('detail'); }}
              disabled={isDisabled || startMutation.isPending}
            />
          )}

          {/* CALIBRATING — waiting for samples to be processed */}
          {view === 'calibrating' && activeJob && (
            <div>
              {activeItems.some((i) => i.status === 'approved' || i.status === 'rejected') ||
              activeJob.status === 'calibrating' ? (
                <CalibrationReview
                  job={activeJob}
                  items={activeItems.filter((i) => i.status === 'calibration' ||
                    i.status === 'approved' || i.status === 'rejected' || i.status === 'failed' || i.status === 'skipped')}
                  onDecision={(itemId, decision) => decisionMutation.mutate({ itemId, decision })}
                  onConfirmRun={() => confirmRunMutation.mutate()}
                  isMutating={confirmRunMutation.isPending}
                />
              ) : (
                /* Still processing calibration samples */
                <div
                  className="rounded-xl p-8 text-center"
                  style={{
                    background: 'var(--color-bg-surface)',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  <svg
                    className="mx-auto mb-4 h-10 w-10 animate-spin"
                    style={{ color: 'var(--color-primary-light)' }}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <p className="text-[15px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Kalibrasyon örnekleri işleniyor...
                  </p>
                  <p className="mt-1.5 text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
                    {(activeJob.config?.sample_size as number | undefined) ?? 10} ürün için SEO optimizasyon taslakları oluşturuluyor.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* RUNNING — live progress */}
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
              onBack={() => { setView('command'); setActiveJobId(null); }}
              isRollingBack={rollbackItemMutation.isPending || rollbackAllMutation.isPending}
            />
          )}

          {/* Loading state when job ID is set but detail not yet loaded */}
          {view === 'detail' && activeJobId && !activeJob && (
            <div className="flex items-center justify-center py-20">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

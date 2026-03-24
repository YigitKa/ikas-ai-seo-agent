import { useState } from 'react';
import type { BatchConfig, BatchJob, BatchStats } from '../../types';
import BatchConfigPanel from './BatchConfigPanel';
import BatchHistory from './BatchHistory';

const DEFAULT_CONFIG: BatchConfig = {
  score_threshold: 70,
  category_filter: '',
  in_stock_only: false,
  preserve_specs: true,
  prevent_cannibalization: true,
  max_title_change_pct: 20,
  sample_size: 10,
  target_fields: ['meta_title', 'meta_description', 'name', 'description', 'description_en'],
};

const STATUS_LABELS: Record<string, string> = {
  idle: 'Boşta',
  calibrating: 'Kalibre Ediliyor',  calibration_done: 'Kalibrasyon Tamamlandı',  running: 'Çalışıyor',
  paused: 'Duraklatıldı',
  completed: 'Tamamlandı',
  failed: 'Hata',
  cancelled: 'İptal Edildi',
};

const STATUS_COLORS: Record<string, string> = {
  idle: 'rgba(100,116,139,0.2)',
  calibrating: 'rgba(245,158,11,0.18)',
  calibration_done: 'rgba(245,158,11,0.18)',
  running: 'rgba(34,197,94,0.18)',
  paused: 'rgba(99,102,241,0.18)',
  completed: 'rgba(34,197,94,0.18)',
  failed: 'rgba(239,68,68,0.18)',
  cancelled: 'rgba(100,116,139,0.2)',
};

const STATUS_TEXT: Record<string, string> = {
  idle: '#94a3b8',
  calibrating: '#f59e0b',
  calibration_done: '#f59e0b',
  running: '#22c55e',
  paused: '#818cf8',
  completed: '#22c55e',
  failed: '#ef4444',
  cancelled: '#94a3b8',
};

interface Props {
  stats: BatchStats;
  jobs: BatchJob[];
  onStartCalibration: (config: BatchConfig) => void;
  onStartDirect: (config: BatchConfig) => void;
  onViewJob: (jobId: string) => void;
  onDeleteJob?: (jobId: string) => void;
  disabled: boolean;
}

function MetricCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
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
      <p className="mt-1 text-[22px] font-bold tabular-nums" style={{ color: 'var(--color-text-primary)' }}>
        {value}
      </p>
      {sub && (
        <p className="mt-0.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          {sub}
        </p>
      )}
    </div>
  );
}

export default function BatchCommandCenter({
  stats,
  jobs,
  onStartCalibration,
  onStartDirect,
  onViewJob,
  onDeleteJob,
  disabled,
}: Props) {
  const [config, setConfig] = useState<BatchConfig>(DEFAULT_CONFIG);

  const activeStatus = stats.active_job?.status ?? 'idle';
  const bgColor = STATUS_COLORS[activeStatus] ?? STATUS_COLORS.idle;
  const textColor = STATUS_TEXT[activeStatus] ?? STATUS_TEXT.idle;

  const avgDelta = stats.avg_score_improvement;
  const activeJob = stats.active_job;
  const isActive = activeJob && (activeJob.status === 'calibrating' || activeJob.status === 'running');

  return (
    <div className="space-y-5">
      {/* Active job banner — prominent when LLM is working */}
      {isActive && activeJob && (
        <div
          className="rounded-xl p-4"
          style={{
            background: activeJob.status === 'calibrating'
              ? 'rgba(245,158,11,0.06)'
              : 'rgba(34,197,94,0.06)',
            border: activeJob.status === 'calibrating'
              ? '1px solid rgba(245,158,11,0.25)'
              : '1px solid rgba(34,197,94,0.25)',
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className="flex h-9 w-9 items-center justify-center rounded-lg"
                style={{
                  background: activeJob.status === 'calibrating'
                    ? 'rgba(245,158,11,0.15)'
                    : 'rgba(34,197,94,0.15)',
                }}
              >
                <svg
                  className="h-5 w-5 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke={activeJob.status === 'calibrating' ? '#f59e0b' : '#22c55e'}
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <div>
                <p className="text-[14px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {activeJob.status === 'calibrating'
                    ? 'Kalibrasyon Devam Ediyor'
                    : 'Toplu Optimizasyon Çalışıyor'}
                </p>
                <p className="mt-0.5 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                  {activeJob.status === 'calibrating' ? (
                    <>
                      AI, <span className="font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                        {activeJob.config?.sample_size ?? '?'}
                      </span> örneklem ürün üzerinde SEO önerileri oluşturuyor
                      {activeJob.processed_count > 0 && (
                        <> — <span className="font-semibold tabular-nums" style={{ color: 'var(--color-primary-light)' }}>
                          {activeJob.processed_count} / {activeJob.config?.sample_size ?? '?'}
                        </span> tamamlandı</>
                      )}
                    </>
                  ) : (
                    <>
                      <span className="font-semibold tabular-nums" style={{ color: 'var(--color-text-secondary)' }}>
                        {activeJob.processed_count}
                      </span>
                      {' / '}
                      <span className="tabular-nums">{activeJob.total_count}</span>
                      {' ürün işlendi'}
                      {activeJob.avg_score_before > 0 && activeJob.avg_score_after > 0 && (
                        <span className="ml-2">
                          · Ort. skor: {activeJob.avg_score_before.toFixed(0)} → {activeJob.avg_score_after.toFixed(0)}
                          <span style={{
                            color: activeJob.avg_score_after > activeJob.avg_score_before ? '#22c55e' : '#ef4444',
                            fontWeight: 600,
                          }}>
                            {' '}({activeJob.avg_score_after > activeJob.avg_score_before ? '+' : ''}
                            {(activeJob.avg_score_after - activeJob.avg_score_before).toFixed(0)})
                          </span>
                        </span>
                      )}
                    </>
                  )}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onViewJob(activeJob.id)}
              className="rounded-lg px-4 py-2 text-[12px] font-semibold text-white transition-opacity hover:opacity-90"
              style={{
                background: activeJob.status === 'calibrating'
                  ? 'linear-gradient(135deg, #f59e0b, #d97706)'
                  : 'linear-gradient(135deg, #22c55e, #16a34a)',
              }}
            >
              {activeJob.status === 'calibrating' ? 'Kalibrasyonu Gör' : 'İlerlemeyi Gör'}
            </button>
          </div>
        </div>
      )}

      {/* Status + metrics row */}
      <div className="grid grid-cols-4 gap-4">
        {/* System status */}
        <div
          className="col-span-1 flex flex-col justify-between rounded-xl p-4"
          style={{
            background: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border)',
          }}
        >
          <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            Sistem Durumu
          </p>
          <div>
            <span
              className="mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold"
              style={{ background: bgColor, color: textColor }}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{
                  background: textColor,
                  animation: activeStatus === 'running' || activeStatus === 'calibrating' ? 'pulse 2s infinite' : 'none',
                }}
              />
              {STATUS_LABELS[activeStatus] ?? activeStatus}
            </span>
          </div>
        </div>

        <MetricCard
          label="Toplam İşlem"
          value={stats.total_jobs}
          sub="tamamlanan döngü"
        />
        <MetricCard
          label="İşlenen Ürün"
          value={stats.total_processed.toLocaleString('tr-TR')}
          sub="toplam optimize edildi"
        />
        <MetricCard
          label="Ort. Skor Artışı"
          value={avgDelta > 0 ? `+${avgDelta.toFixed(1)}` : avgDelta.toFixed(1)}
          sub="puan iyileştirme"
        />
      </div>

      {/* Config + History side by side */}
      <div className="grid grid-cols-5 gap-5">
        <div className="col-span-3">
          <BatchConfigPanel
            config={config}
            onChange={setConfig}
            onStartCalibration={() => onStartCalibration(config)}
            onStartDirect={() => onStartDirect(config)}
            disabled={disabled}
          />
        </div>
        <div className="col-span-2">
          <BatchHistory jobs={jobs.slice(0, 8)} onSelect={onViewJob} onDelete={onDeleteJob} />
        </div>
      </div>
    </div>
  );
}

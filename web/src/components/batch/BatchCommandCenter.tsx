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
};

const STATUS_LABELS: Record<string, string> = {
  idle: 'Boşta',
  calibrating: 'Kalibre Ediliyor',
  running: 'Çalışıyor',
  paused: 'Duraklatıldı',
  completed: 'Tamamlandı',
  failed: 'Hata',
  cancelled: 'İptal Edildi',
};

const STATUS_COLORS: Record<string, string> = {
  idle: 'rgba(100,116,139,0.2)',
  calibrating: 'rgba(245,158,11,0.18)',
  running: 'rgba(34,197,94,0.18)',
  paused: 'rgba(99,102,241,0.18)',
  completed: 'rgba(34,197,94,0.18)',
  failed: 'rgba(239,68,68,0.18)',
  cancelled: 'rgba(100,116,139,0.2)',
};

const STATUS_TEXT: Record<string, string> = {
  idle: '#94a3b8',
  calibrating: '#f59e0b',
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
  disabled,
}: Props) {
  const [config, setConfig] = useState<BatchConfig>(DEFAULT_CONFIG);

  const activeStatus = stats.active_job?.status ?? 'idle';
  const bgColor = STATUS_COLORS[activeStatus] ?? STATUS_COLORS.idle;
  const textColor = STATUS_TEXT[activeStatus] ?? STATUS_TEXT.idle;

  const avgDelta = stats.avg_score_improvement;

  return (
    <div className="space-y-5">
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
          <BatchHistory jobs={jobs.slice(0, 8)} onSelect={onViewJob} />
        </div>
      </div>
    </div>
  );
}

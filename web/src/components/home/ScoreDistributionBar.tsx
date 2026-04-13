import { useState, useEffect } from 'react';
import type { ScoreDistributionBucket } from '../../types';

const BUCKET_COLORS: Record<string, string> = {
  '90-100': 'var(--color-success)',
  '80-89': 'var(--color-accent)',
  '70-79': '#3b82f6',
  '60-69': 'var(--color-warning)',
  '50-59': 'var(--color-orange)',
  '0-49': 'var(--color-danger)',
};

const BUCKET_ORDER = ['90-100', '80-89', '70-79', '60-69', '50-59', '0-49'];

interface ScoreDistributionBarProps {
  distribution?: ScoreDistributionBucket[];
  isLoading: boolean;
}

export default function ScoreDistributionBar({ distribution, isLoading }: ScoreDistributionBarProps) {
  const [hoveredBucket, setHoveredBucket] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    let r1: number, r2: number;
    r1 = requestAnimationFrame(() => { r2 = requestAnimationFrame(() => setMounted(true)); });
    return () => { cancelAnimationFrame(r1); cancelAnimationFrame(r2); };
  }, []);

  if (isLoading) {
    return <div className="enterprise-surface animate-pulse rounded-2xl" style={{ height: 72 }} />;
  }

  const buckets = BUCKET_ORDER.map((key) => ({
    bucket: key,
    count: distribution?.find((d) => d.bucket === key)?.count ?? 0,
  }));

  const total = buckets.reduce((sum, b) => sum + b.count, 0);
  if (total === 0) return null;

  return (
    <div
      className="enterprise-surface rounded-2xl p-4"
      style={{
        background: 'linear-gradient(160deg, var(--surface-panel), var(--surface-raised))',
        border: '1px solid var(--color-divider)',
      }}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[13px] font-semibold uppercase tracking-widest" style={{ color: 'var(--color-text-secondary)' }}>
          Katalog Skor Dagilimi
        </span>
        <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
          {total} urun
        </span>
      </div>

      {/* Stacked bar */}
      <div className="relative flex h-7 overflow-hidden rounded-full" style={{ background: 'var(--surface-raised)' }}>
        {buckets.map((b) => {
          const pct = (b.count / total) * 100;
          if (pct === 0) return null;
          const isHovered = hoveredBucket === b.bucket;
          return (
            <div
              key={b.bucket}
              className="relative"
              style={{
                width: mounted ? `${pct}%` : '0%',
                background: BUCKET_COLORS[b.bucket],
                opacity: hoveredBucket && !isHovered ? 0.4 : 0.85,
                transform: isHovered ? 'scaleY(1.15)' : 'scaleY(1)',
                transition: 'width 1s cubic-bezier(0.4,0,0.2,1), opacity 0.3s, transform 0.3s',
              }}
              onMouseEnter={() => setHoveredBucket(b.bucket)}
              onMouseLeave={() => setHoveredBucket(null)}
            >
              {/* Tooltip */}
              {isHovered && (
                <div
                  className="absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[11px] font-medium shadow-lg"
                  style={{
                    background: 'var(--surface-code)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  {b.bucket} puan: {b.count} urun ({pct.toFixed(0)}%)
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
        {buckets.filter((b) => b.count > 0).map((b) => (
          <div key={b.bucket} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: BUCKET_COLORS[b.bucket] }}
            />
            <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {b.bucket}: {b.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

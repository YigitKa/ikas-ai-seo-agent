import CircularScore from '../../shared/ui/CircularScore';
import { getScoreColor } from '../../shared/score/scoreUtils';
import TrendSparkline from './TrendSparkline';
import type { ReportSummary, DailyStoreTrend } from '../../types';

const PILLARS = [
  {
    key: 'seo',
    label: 'SEO',
    trendKey: 'avg_seo',
    description: 'Arama motoru gorunurlugu ve meta sinyalleri',
  },
  {
    key: 'geo',
    label: 'GEO',
    trendKey: 'avg_geo',
    description: 'AI alintilama ve generative engine uyumu',
  },
  {
    key: 'aeo',
    label: 'AEO',
    trendKey: 'avg_aeo',
    description: 'Yanitlanabilirlik ve answer-engine uyumu',
  },
] as const;

interface ScorePulseRowProps {
  summary?: ReportSummary;
  trends?: DailyStoreTrend[];
  isLoading: boolean;
}

export default function ScorePulseRow({ summary, trends, isLoading }: ScorePulseRowProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {PILLARS.map((p) => (
          <div key={p.key} className="enterprise-surface animate-pulse rounded-2xl p-5" style={{ minHeight: 100 }} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {PILLARS.map((pillar, idx) => {
        const score = Math.round(summary?.latest_avg?.[pillar.key] ?? 0);
        const delta = summary?.improvement?.[pillar.key] ?? 0;
        const trendData = trends?.map((t) => (t as unknown as Record<string, number>)[pillar.trendKey] ?? 0) ?? [];
        const color = getScoreColor(score);

        return (
          <div
            key={pillar.key}
            className="enterprise-surface rounded-2xl px-4 py-3.5 transition-all duration-200 hover:-translate-y-0.5"
            style={{
              background: 'linear-gradient(160deg, rgba(15,23,42,0.88), rgba(30,41,59,0.62))',
              border: '1px solid rgba(148,163,184,0.14)',
            }}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[16px] font-bold uppercase tracking-widest" style={{ color }}>
                  {pillar.label}
                </div>
                <div className="mt-0.5 text-[13px] leading-5" style={{ color: 'var(--color-text-muted)' }}>
                  {pillar.description}
                </div>
              </div>
              <CircularScore score={score} size={84} animated delay={300 + idx * 150} />
            </div>

            <div className="mt-2.5 flex items-center justify-between">
              <TrendSparkline data={trendData} color={color} width={110} height={28} />
              {delta !== 0 && (
                <span
                  className="rounded-full px-2.5 py-1 text-[12px] font-bold"
                  style={{
                    background: delta > 0 ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
                    color: delta > 0 ? '#34d399' : '#f87171',
                  }}
                >
                  {delta > 0 ? '+' : ''}{delta.toFixed(1)}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

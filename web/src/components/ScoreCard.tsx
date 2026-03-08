import type { SeoScore } from '../types';

interface Props {
  score: SeoScore;
}

const FIELDS = [
  { key: 'title_score', label: 'Baslik', max: 15, icon: 'T' },
  { key: 'description_score', label: 'Aciklama', max: 20, icon: 'A' },
  { key: 'english_description_score', label: 'EN Aciklama', max: 5, icon: 'E' },
  { key: 'meta_score', label: 'Meta Title', max: 15, icon: 'M' },
  { key: 'meta_desc_score', label: 'Meta Desc', max: 10, icon: 'D' },
  { key: 'keyword_score', label: 'Keyword', max: 10, icon: 'K' },
  { key: 'content_quality_score', label: 'Icerik Kalite', max: 10, icon: 'Q' },
  { key: 'technical_seo_score', label: 'Teknik SEO', max: 10, icon: 'S' },
  { key: 'readability_score', label: 'Okunabilirlik', max: 5, icon: 'R' },
] as const;

function getScoreColor(pct: number): string {
  if (pct >= 80) return '#10b981';
  if (pct >= 60) return '#f59e0b';
  if (pct >= 40) return '#f97316';
  return '#ef4444';
}

function getScoreGradient(pct: number): string {
  if (pct >= 80) return 'linear-gradient(135deg, #10b981, #06b6d4)';
  if (pct >= 60) return 'linear-gradient(135deg, #f59e0b, #f97316)';
  if (pct >= 40) return 'linear-gradient(135deg, #f97316, #ef4444)';
  return 'linear-gradient(135deg, #ef4444, #dc2626)';
}

function CircularScore({ score }: { score: number }) {
  const size = 100;
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = getScoreColor(score);

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="score-ring" width={size} height={size}>
        <circle
          className="score-ring-track"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
        />
        <circle
          className="score-ring-fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold" style={{ color }}>
          {score}
        </span>
        <span className="text-[9px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
          /100
        </span>
      </div>
    </div>
  );
}

export default function ScoreCard({ score }: Props) {
  return (
    <div
      className="rounded-xl p-5"
      style={{
        background: 'var(--glass-bg)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div className="flex gap-6">
        {/* Circular Score */}
        <div className="flex flex-col items-center gap-1.5">
          <CircularScore score={score.total_score} />
          <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            SEO Skoru
          </span>
        </div>

        {/* Metrics Grid */}
        <div className="flex-1 grid grid-cols-3 gap-x-5 gap-y-2">
          {FIELDS.map(({ key, label, max }) => {
            const val = score[key] as number;
            const pct = (val / max) * 100;
            const color = getScoreColor(pct);

            return (
              <div key={key} className="min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-medium truncate" style={{ color: 'var(--color-text-secondary)' }}>
                    {label}
                  </span>
                  <span className="text-[11px] font-semibold ml-1.5" style={{ color }}>
                    {val}<span style={{ color: 'var(--color-text-muted)' }}>/{max}</span>
                  </span>
                </div>
                <div
                  className="h-1 w-full rounded-full overflow-hidden"
                  style={{ background: 'rgba(255,255,255,0.06)' }}
                >
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${pct}%`,
                      background: getScoreGradient(pct),
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Issues */}
      {score.issues.length > 0 && (
        <details className="mt-4">
          <summary
            className="cursor-pointer text-xs font-medium flex items-center gap-1.5"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            {score.issues.length} sorun tespit edildi
          </summary>
          <ul className="mt-2.5 space-y-1.5 pl-1">
            {score.issues.map((issue, i) => (
              <li key={i} className="flex items-start gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                <span className="mt-0.5 h-1 w-1 flex-shrink-0 rounded-full" style={{ background: 'var(--color-danger)' }} />
                {issue}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

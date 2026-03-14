import type { SeoScore } from '../types';
import { SCORE_FIELDS, SUMMARY_FIELDS, explainIssue, getFieldStatusText, getScoreColor } from '../shared/score/scoreUtils';
import CircularScore from '../shared/ui/CircularScore';
import ProgressBar from '../shared/ui/ProgressBar';

interface Props {
  score: SeoScore;
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
      <div className="flex items-center gap-4 pb-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <CircularScore score={score.total_score} size={104} strokeWidth={6} />
        <div className="min-w-0 flex-1">
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.18em]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            SEO Skoru
          </div>
          <div className="mt-1 text-[18px] font-semibold text-white">
            Genel durum: {getFieldStatusText(score.total_score)}
          </div>
          <p className="mt-2 text-[12px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
            Asagidaki her satir, SEO puaninin hangi alandan geldigini ve o alanin neyi olctugunu aciklar.
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {SUMMARY_FIELDS.map(({ key, label, description }) => {
          const value = score[key as keyof SeoScore] as number;
          const color = getScoreColor(value);

          return (
            <div
              key={key}
              className="rounded-xl px-4 py-3"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div
                    className="text-[11px] font-semibold uppercase tracking-[0.16em]"
                    style={{ color }}
                  >
                    {label}
                  </div>
                  <p className="mt-1 text-[12px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
                    {description}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-[22px] font-semibold" style={{ color }}>
                    {value}
                  </div>
                  <div className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                    /100
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 space-y-3">
        {SCORE_FIELDS.map(({ key, label, max, description }) => {
          const val = score[key] as number;
          const pct = (val / max) * 100;
          const color = getScoreColor(pct);

          return (
            <div
              key={key}
              className="rounded-xl px-4 py-3"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold text-white">{label}</div>
                  <p className="mt-1 text-[12px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
                    {description}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-[14px] font-semibold" style={{ color }}>
                    {val}<span style={{ color: 'var(--color-text-muted)' }}>/{max}</span>
                  </div>
                  <div className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                    {getFieldStatusText(pct)}
                  </div>
                </div>
              </div>

              <div className="mt-3">
                <ProgressBar pct={pct} height="h-1.5" />
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-5">
        <div
          className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Tespit Edilen Sorunlar ({score.issues.length})
        </div>

        {score.issues.length > 0 ? (
          <div className="space-y-3">
            {score.issues.map((issue, index) => (
              <div
                key={`${issue}-${index}`}
                className="rounded-xl px-4 py-3"
                style={{
                  background: 'rgba(239, 68, 68, 0.05)',
                  border: '1px solid rgba(239, 68, 68, 0.12)',
                }}
              >
                <div className="flex items-start gap-2">
                  <span
                    className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full"
                    style={{ background: 'var(--score-poor)' }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-[12px] font-medium text-white">{issue}</div>
                    <p className="mt-1 text-[12px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
                      {explainIssue(issue)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            className="rounded-xl px-4 py-3 text-[12px]"
            style={{
              background: 'rgba(16, 185, 129, 0.06)',
              border: '1px solid rgba(16, 185, 129, 0.14)',
              color: '#a7f3d0',
            }}
          >
            Bu urun icin kritik bir SEO sorunu tespit edilmedi.
          </div>
        )}
      </div>
    </div>
  );
}

import { memo, useState } from 'react';
import type { SeoScore } from '../../types';
import {
  getScoreColor,
  getFieldStatusText,
  getStatusBadgeStyle,
} from '../../shared/score/scoreUtils';
import CircularScore, { useCountUp } from '../../shared/ui/CircularScore';
import ProgressBar from '../../shared/ui/ProgressBar';

// ── Style helpers ────────────────────────────────────────────────────────────

function getCategoryCardStyle(accent: string): {
  background: string;
  border: string;
  boxShadow: string;
} {
  return {
    background: `radial-gradient(circle at top right, ${accent}1c, transparent 36%), linear-gradient(180deg, rgba(15,23,42,0.94), rgba(15,23,42,0.82))`,
    border: `1px solid ${accent}2c`,
    boxShadow: `0 14px 28px ${accent}12`,
  };
}

function getCategoryHintStyle(accent: string): {
  background: string;
  border: string;
  color: string;
} {
  return {
    background: `${accent}14`,
    border: `1px solid ${accent}22`,
    color: accent,
  };
}

// ── Category definitions ────────────────────────────────────────────────────

const CATEGORIES = [
  {
    key: 'seo_score' as const,
    label: 'SEO',
    accent: '#6366f1',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
    description: 'Google gorunurlugu, meta alanlar ve teknik sayfa temeli.',
  },
  {
    key: 'geo_score' as const,
    label: 'GEO',
    accent: '#06b6d4',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
      </svg>
    ),
    description: 'Yapay zeka motorlarinin icerigi anlamasi ve kaynak gostermesi.',
  },
  {
    key: 'aeo_score' as const,
    label: 'AEO',
    accent: 'var(--score-good)',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
      </svg>
    ),
    description: 'Soru-cevap uyumu, net anlatim ve cevap uretilebilirligi.',
  },
] as const;

const FIELDS = [
  { key: 'title_score' as const, label: 'Baslik', max: 15 },
  { key: 'description_score' as const, label: 'Aciklama', max: 20 },
  { key: 'english_description_score' as const, label: 'EN Aciklama', max: 5 },
  { key: 'meta_score' as const, label: 'Meta Title', max: 15 },
  { key: 'meta_desc_score' as const, label: 'Meta Desc', max: 10 },
  { key: 'keyword_score' as const, label: 'Keyword', max: 10 },
  { key: 'content_quality_score' as const, label: 'Icerik Kalitesi', max: 10 },
  { key: 'technical_seo_score' as const, label: 'Teknik SEO', max: 10 },
  { key: 'readability_score' as const, label: 'Okunabilirlik', max: 5 },
  { key: 'ai_citability_score' as const, label: 'AI Alintilanabilirlik', max: 10 },
] as const;

// ── CategoryCard ────────────────────────────────────────────────────────────

function CategoryCard({
  cat,
  value,
  index,
}: {
  cat: typeof CATEGORIES[number];
  value: number;
  index: number;
}) {
  const color = getScoreColor(value);
  const displayVal = useCountUp(value, 1000, 400 + index * 200);
  const statusText = getFieldStatusText(value);
  const statusBadge = getStatusBadgeStyle(value);
  const cardStyle = getCategoryCardStyle(cat.accent);

  return (
    <div
      className="score-section-enter relative overflow-hidden rounded-2xl px-4 py-4"
      style={{
        animationDelay: `${300 + index * 150}ms`,
        ...cardStyle,
      }}
    >
      <div
        className="absolute -right-6 -top-8 h-24 w-24 rounded-full blur-3xl"
        style={{ background: `${cat.accent}22` }}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-xl"
            style={{ background: `${cat.accent}20`, color: cat.accent }}
          >
            {cat.icon}
          </div>
          <div>
            <div
              className="text-[10px] font-semibold uppercase tracking-[0.16em]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Kategori
            </div>
            <div className="text-[14px] font-semibold" style={{ color: cat.accent }}>
              {cat.label}
            </div>
          </div>
        </div>
        <span
          className="rounded-full px-2 py-1 text-[10px] font-semibold"
          style={statusBadge}
        >
          {statusText}
        </span>
      </div>
      <div className="relative mt-4 flex items-end gap-1.5">
        <span className="text-[30px] font-bold leading-none" style={{ color }}>
          {displayVal}
        </span>
        <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
          /100
        </span>
      </div>
      <p className="relative mt-2 text-[12px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
        {cat.description}
      </p>
      <div className="relative mt-3">
        <ProgressBar pct={value} animated delay={700 + index * 150} />
      </div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────

function SeoScoreChatMessage({ score }: { score: SeoScore }) {
  const [issuesOpen, setIssuesOpen] = useState(false);
  const totalPct = score.total_score;
  const statusText = getFieldStatusText(totalPct);
  const statusBadge = getStatusBadgeStyle(totalPct);
  const totalColor = getScoreColor(totalPct);
  const categoryScores = CATEGORIES.map((cat) => ({
    ...cat,
    value: score[cat.key],
  }));
  const strongestCategory = categoryScores.reduce((best, current) =>
    current.value > best.value ? current : best,
  );
  const weakestCategory = categoryScores.reduce((worst, current) =>
    current.value < worst.value ? current : worst,
  );

  return (
    <div className="score-chat-message mr-6 space-y-0">
      {/* Role label */}
      <div
        className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        SEO Analiz
      </div>

      <div
        className="overflow-hidden rounded-xl"
        style={{
          background: 'var(--color-bg-elevated)',
          border: '1px solid var(--color-border)',
        }}
      >
        {/* ── Header with total score ── */}
        <div
          className="score-section-enter flex flex-col items-start gap-4 px-5 py-5 sm:flex-row sm:items-center"
          style={{
            borderBottom: '1px solid rgba(255,255,255,0.04)',
            animationDelay: '0ms',
          }}
        >
          <CircularScore score={totalPct} size={76} strokeWidth={5} animated delay={200} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
                style={statusBadge}
              >
                {statusText}
              </span>
              <span
                className="text-[22px] font-bold"
                style={{ color: totalColor }}
              >
                {score.total_score}
              </span>
              <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>/100</span>
            </div>
            <p className="mt-1.5 text-[12px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
              Genel skor; SEO, GEO ve AEO basliklarinin birlikte ne kadar dengeli oldugunu gosterir.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
                style={getCategoryHintStyle(strongestCategory.accent)}
              >
                En guclu: {strongestCategory.label} {strongestCategory.value}/100
              </span>
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
                style={getCategoryHintStyle(weakestCategory.accent)}
              >
                Odaklanilacak alan: {weakestCategory.label} {weakestCategory.value}/100
              </span>
            </div>
          </div>
        </div>

        {/* ── Three category cards ── */}
        <div
          className="px-4 pb-4"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {CATEGORIES.map((cat, i) => (
              <CategoryCard
                key={cat.key}
                cat={cat}
                value={score[cat.key]}
                index={i}
              />
            ))}
          </div>
        </div>

        {/* ── Field breakdown ── */}
        <div className="px-4 py-3">
          <div
            className="score-section-enter mb-2.5 text-[10px] font-semibold uppercase tracking-[0.16em]"
            style={{ color: 'var(--color-text-muted)', animationDelay: '700ms' }}
          >
            Alan Detaylari
          </div>
          <div className="space-y-2">
            {FIELDS.map((field, i) => {
              const val = score[field.key] as number;
              const pct = (val / field.max) * 100;
              const color = getScoreColor(pct);
              const badge = getStatusBadgeStyle(pct);
              const baseDelay = 800 + i * 60;

              return (
                <div
                  key={field.key}
                  className="score-field-enter"
                  style={{ animationDelay: `${baseDelay}ms` }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-medium text-white">{field.label}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold" style={{ color }}>
                        {val}<span style={{ color: 'var(--color-text-muted)' }}>/{field.max}</span>
                      </span>
                      <span
                        className="rounded px-1.5 py-0.5 text-[9px] font-semibold"
                        style={badge}
                      >
                        {getFieldStatusText(pct)}
                      </span>
                    </div>
                  </div>
                  <div className="mt-1">
                    <ProgressBar pct={pct} animated delay={baseDelay + 200} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Issues (collapsible) ── */}
        {score.issues.length > 0 && (
          <div
            className="score-section-enter"
            style={{
              borderTop: '1px solid rgba(255,255,255,0.04)',
              animationDelay: `${800 + FIELDS.length * 60 + 100}ms`,
            }}
          >
            <button
              type="button"
              onClick={() => setIssuesOpen(!issuesOpen)}
              className="flex w-full items-center gap-2 px-4 py-2.5 text-left transition-colors hover:bg-white/[.02]"
            >
              <svg
                className="h-3 w-3 transition-transform duration-200"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
                style={{
                  color: 'var(--score-poor)',
                  transform: issuesOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                }}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
              <span className="text-[11px] font-semibold" style={{ color: '#f87171' }}>
                {score.issues.length} sorun tespit edildi
              </span>
            </button>

            {issuesOpen && (
              <div className="space-y-1.5 px-4 pb-3">
                {score.issues.map((issue, index) => (
                  <div
                    key={`${issue}-${index}`}
                    className="score-field-enter flex items-start gap-2 rounded-lg px-3 py-2"
                    style={{
                      background: 'rgba(239, 68, 68, 0.04)',
                      border: '1px solid rgba(239, 68, 68, 0.08)',
                      animationDelay: `${index * 50}ms`,
                    }}
                  >
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full" style={{ background: 'var(--score-poor)' }} />
                    <span className="text-[11px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
                      {issue}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(SeoScoreChatMessage, (prev, next) =>
  prev.score.product_id === next.score.product_id &&
  prev.score.total_score === next.score.total_score,
);

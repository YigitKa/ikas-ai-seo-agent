import { useEffect, useRef, useState } from 'react';
import type { SeoScore } from '../../types';

// ── Helpers ──────────────────────────────────────────────────────────────────

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

function getFieldStatusText(pct: number): string {
  if (pct >= 80) return 'Guclu';
  if (pct >= 60) return 'Gelistirilebilir';
  if (pct >= 40) return 'Zayif';
  return 'Kritik';
}

function getStatusBadgeStyle(pct: number): { background: string; color: string } {
  if (pct >= 80) return { background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' };
  if (pct >= 60) return { background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' };
  if (pct >= 40) return { background: 'rgba(249, 115, 22, 0.15)', color: '#fb923c' };
  return { background: 'rgba(239, 68, 68, 0.15)', color: '#f87171' };
}

// ── useCountUp hook ─────────────────────────────────────────────────────────

function useCountUp(target: number, duration: number, delay: number): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    let startTime: number | null = null;

    const animate = (timestamp: number) => {
      if (startTime === null) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    const delayTimer = setTimeout(() => {
      rafRef.current = requestAnimationFrame(animate);
    }, delay);

    return () => {
      clearTimeout(delayTimer);
      cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration, delay]);

  return value;
}

// ── AnimatedCircularScore ───────────────────────────────────────────────────

function AnimatedCircularScore({
  score,
  size = 72,
  strokeWidth = 5,
  delay = 0,
}: {
  score: number;
  size?: number;
  strokeWidth?: number;
  delay?: number;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const displayValue = useCountUp(score, 1200, delay);
  const color = getScoreColor(score);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  const offset = mounted
    ? circumference - (score / 100) * circumference
    : circumference;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: `stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1) ${delay}ms`,
          }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-lg font-bold" style={{ color }}>{displayValue}</span>
        <span className="text-[9px] font-medium" style={{ color: 'var(--color-text-muted)' }}>/100</span>
      </div>
    </div>
  );
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
    description: 'Arama motoru gorunurlugu, meta sinyalleri ve teknik uygunluk.',
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
    description: 'AI alintilanabilirlik ve generative engine uygunlugu.',
  },
  {
    key: 'aeo_score' as const,
    label: 'AEO',
    accent: '#f59e0b',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
      </svg>
    ),
    description: 'Yanitlanabilirlik, icerik netligi ve answer-engine uyumu.',
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

// ── AnimatedProgressBar ─────────────────────────────────────────────────────

function AnimatedProgressBar({
  pct,
  delay,
}: {
  pct: number;
  delay: number;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setMounted(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  return (
    <div
      className="h-1 w-full overflow-hidden rounded-full"
      style={{ background: 'rgba(255,255,255,0.06)' }}
    >
      <div
        className="h-full rounded-full"
        style={{
          width: mounted ? `${pct}%` : '0%',
          background: getScoreGradient(pct),
          transition: `width 800ms cubic-bezier(0.4, 0, 0.2, 1) ${delay}ms`,
        }}
      />
    </div>
  );
}

// ── CategoryCard (extracted so useCountUp can be called as a hook) ─────────

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

  return (
    <div
      className="score-section-enter relative px-4 py-3"
      style={{
        animationDelay: `${300 + index * 150}ms`,
        borderRight: index < 2 ? '1px solid rgba(255,255,255,0.04)' : 'none',
      }}
    >
      <div
        className="absolute inset-x-0 top-0 h-[2px]"
        style={{ background: `linear-gradient(90deg, ${cat.accent}, transparent)`, opacity: 0.5 }}
      />
      <div className="flex items-center gap-1.5">
        <div
          className="flex h-5 w-5 items-center justify-center rounded"
          style={{ background: `${cat.accent}22`, color: cat.accent }}
        >
          {cat.icon}
        </div>
        <span className="text-[11px] font-bold uppercase tracking-[0.14em]" style={{ color: cat.accent }}>
          {cat.label}
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-[20px] font-bold" style={{ color }}>{displayVal}</span>
        <span className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>/100</span>
      </div>
      <p className="mt-1 text-[10px] leading-snug" style={{ color: 'var(--color-text-muted)' }}>
        {cat.description}
      </p>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────

export default function SeoScoreChatMessage({ score }: { score: SeoScore }) {
  const [issuesOpen, setIssuesOpen] = useState(false);
  const totalPct = score.total_score;
  const statusText = getFieldStatusText(totalPct);
  const statusBadge = getStatusBadgeStyle(totalPct);
  const totalColor = getScoreColor(totalPct);

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
          className="score-section-enter flex items-center gap-4 px-5 py-4"
          style={{
            borderBottom: '1px solid rgba(255,255,255,0.04)',
            animationDelay: '0ms',
          }}
        >
          <AnimatedCircularScore score={totalPct} size={76} strokeWidth={5} delay={200} />
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
              Urunun genel SEO durumu ve alt boyutlardaki dagilim.
            </p>
          </div>
        </div>

        {/* ── Three category cards ── */}
        <div
          className="grid grid-cols-3 gap-0"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
        >
          {CATEGORIES.map((cat, i) => (
            <CategoryCard
              key={cat.key}
              cat={cat}
              value={score[cat.key]}
              index={i}
            />
          ))}
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
                    <AnimatedProgressBar pct={pct} delay={baseDelay + 200} />
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
                  color: '#ef4444',
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
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full" style={{ background: '#ef4444' }} />
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

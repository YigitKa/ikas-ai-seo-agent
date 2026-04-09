import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getScoreColor } from '../../shared/score/scoreUtils';
import { useCountUp } from '../../shared/ui/CircularScore';
import type { ProductListResponse } from '../../types';

const BADGE_SIZE = 44;
const STROKE = 3;
const RADIUS = (BADGE_SIZE - STROKE) / 2;
const CIRC = 2 * Math.PI * RADIUS;

function ScoreBadge({ score, delay = 0 }: { score: number; delay?: number }) {
  const color = getScoreColor(score);
  const displayed = useCountUp(score, 900, delay);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    let r1: number, r2: number;
    r1 = requestAnimationFrame(() => { r2 = requestAnimationFrame(() => setMounted(true)); });
    return () => { cancelAnimationFrame(r1); cancelAnimationFrame(r2); };
  }, []);

  const offset = mounted ? CIRC - (score / 100) * CIRC : CIRC;

  return (
    <div className="relative flex-shrink-0" style={{ width: BADGE_SIZE, height: BADGE_SIZE }}>
      <svg width={BADGE_SIZE} height={BADGE_SIZE} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={BADGE_SIZE / 2} cy={BADGE_SIZE / 2} r={RADIUS} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={STROKE} />
        <circle
          cx={BADGE_SIZE / 2} cy={BADGE_SIZE / 2} r={RADIUS} fill="none"
          stroke={color} strokeWidth={STROKE} strokeLinecap="round"
          strokeDasharray={CIRC} strokeDashoffset={offset}
          style={{ transition: `stroke-dashoffset 1s cubic-bezier(0.4,0,0.2,1) ${delay}ms` }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[13px] font-bold tabular-nums" style={{ color }}>{displayed}</span>
      </div>
    </div>
  );
}

interface NeedsAttentionSectionProps {
  lowProducts?: ProductListResponse;
  isLoading: boolean;
}

export default function NeedsAttentionSection({ lowProducts, isLoading }: NeedsAttentionSectionProps) {
  const navigate = useNavigate();
  const items = lowProducts?.items ?? [];
  const totalCount = lowProducts?.total_count ?? 0;

  if (isLoading) {
    return (
      <div
        className="enterprise-surface animate-pulse rounded-2xl"
        style={{ minHeight: 300, background: 'rgba(15,23,42,0.6)' }}
      />
    );
  }

  const allGood = totalCount === 0 || (items.length > 0 && (items[0]?.score?.total_score ?? 0) >= 70);

  return (
    <div
      className="enterprise-surface overflow-hidden rounded-2xl"
      style={{
        background: 'linear-gradient(160deg, rgba(15,23,42,0.88), rgba(30,41,59,0.62))',
        border: '1px solid rgba(148,163,184,0.14)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: '1px solid rgba(148,163,184,0.08)' }}
      >
        <div className="flex items-center gap-2.5">
          <span className="text-[14px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Dikkat Gerektiren Urunler
          </span>
          {!allGood && totalCount > 0 && (
            <span
              className="rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums"
              style={{
                background: 'rgba(239,68,68,0.12)',
                color: '#f87171',
                border: '1px solid rgba(239,68,68,0.2)',
              }}
            >
              {totalCount}
            </span>
          )}
        </div>
        {!allGood && (
          <button
            onClick={() => navigate('/workspace')}
            className="flex items-center gap-1 text-[12px] font-medium transition-opacity hover:opacity-70"
            style={{ color: '#a5b4fc' }}
          >
            Tumunu Incele
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        )}
      </div>

      {/* List */}
      {allGood ? (
        <div className="flex items-center gap-3 px-4 py-5">
          <svg
            className="h-5 w-5 flex-shrink-0"
            style={{ color: '#34d399' }}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-[13px]" style={{ color: '#34d399' }}>
            Tum urunleriniz iyi durumda!
          </span>
        </div>
      ) : (
        <div className="divide-y" style={{ borderColor: 'rgba(148,163,184,0.06)' }}>
          {items.map((item, idx) => {
            const score = item.score?.total_score ?? 0;
            const topIssue = item.score?.issues?.[0];
            const label = item.product.category || null;

            return (
              <div
                key={item.product.id}
                className="flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-white/[0.025]"
                style={{ animationDelay: `${idx * 40}ms` }}
              >
                <ScoreBadge score={score} delay={80 + idx * 60} />

                <div className="min-w-0 flex-1">
                  <div
                    className="truncate text-[14px] font-medium leading-tight"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {item.product.name}
                  </div>
                  <div
                    className="mt-0.5 truncate text-[13px] leading-tight"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {topIssue ?? label ?? 'Sorun tespit edilemedi'}
                  </div>
                </div>

                <button
                  onClick={() => navigate(`/workspace?product=${item.product.id}`)}
                  className="flex-shrink-0 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all hover:brightness-110"
                  style={{
                    background: 'rgba(99,102,241,0.1)',
                    color: '#a5b4fc',
                    border: '1px solid rgba(99,102,241,0.18)',
                  }}
                >
                  Incele
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

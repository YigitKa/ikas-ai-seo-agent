import { useNavigate } from 'react-router-dom';
import CircularScore from '../../shared/ui/CircularScore';
import { EnterpriseButton } from '../../shared/ui/EnterprisePrimitives';
import type { ProductListResponse, DailyActivity } from '../../types';

interface NeedsAttentionSectionProps {
  lowProducts?: ProductListResponse;
  activity?: DailyActivity[];
  isLoading: boolean;
}

export default function NeedsAttentionSection({
  lowProducts,
  activity,
  isLoading,
}: NeedsAttentionSectionProps) {
  const navigate = useNavigate();
  const items = lowProducts?.items ?? [];
  const recentActivity = (activity ?? []).slice(-7);

  if (isLoading) {
    return <div className="enterprise-surface animate-pulse rounded-2xl" style={{ minHeight: 180 }} />;
  }

  const allGood = items.length === 0 || (items[0]?.score?.total_score ?? 0) >= 70;

  return (
    <div
      className="enterprise-surface rounded-2xl p-4 sm:p-5"
      style={{
        background: 'linear-gradient(160deg, rgba(15,23,42,0.88), rgba(30,41,59,0.62))',
        border: '1px solid rgba(148,163,184,0.14)',
      }}
    >
      {/* Products needing attention */}
      <div className="mb-2 flex items-center justify-between">
        <span
          className="text-[11px] font-semibold uppercase tracking-widest"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Dikkat Gerektiren Urunler
        </span>
        {!allGood && (
          <EnterpriseButton
            size="sm"
            tone="neutral"
            onClick={() => navigate('/workspace')}
          >
            Tumunu Gor
          </EnterpriseButton>
        )}
      </div>

      {allGood ? (
        <div className="flex items-center gap-3 rounded-xl p-4" style={{ background: 'rgba(16,185,129,0.08)' }}>
          <svg className="h-5 w-5 flex-shrink-0" style={{ color: '#34d399' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-[13px]" style={{ color: '#34d399' }}>
            Tum urunleriniz iyi durumda!
          </span>
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2" style={{ scrollSnapType: 'x mandatory' }}>
          {items.slice(0, 6).map((item) => {
            const score = item.score?.total_score ?? 0;
            const topIssue = item.score?.issues?.[0];
            return (
              <div
                key={item.product.id}
                className="flex min-w-[200px] max-w-[240px] flex-shrink-0 flex-col gap-2 rounded-xl p-3 transition-all duration-200 hover:-translate-y-0.5"
                style={{
                  background: 'rgba(15,23,42,0.6)',
                  border: '1px solid rgba(148,163,184,0.1)',
                  scrollSnapAlign: 'start',
                }}
              >
                <div className="flex items-center gap-2.5">
                  <CircularScore score={score} size={48} animated delay={200} />
                  <div className="min-w-0 flex-1">
                    <div
                      className="truncate text-[12px] font-medium"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {item.product.name}
                    </div>
                    {item.product.category && (
                      <div
                        className="truncate text-[10px]"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {item.product.category}
                      </div>
                    )}
                  </div>
                </div>
                {topIssue && (
                  <div className="text-[10px] leading-3.5" style={{ color: 'var(--color-text-secondary)' }}>
                    {topIssue}
                  </div>
                )}
                <button
                  className="mt-auto rounded-lg px-2 py-1 text-[10px] font-medium transition-colors hover:brightness-110"
                  style={{
                    background: 'rgba(99,102,241,0.12)',
                    color: '#a5b4fc',
                    border: '1px solid rgba(99,102,241,0.2)',
                  }}
                  onClick={() => navigate(`/workspace?product=${item.product.id}`)}
                >
                  Incele
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Activity summary */}
      {recentActivity.length > 0 && (
        <>
          <div
            className="my-3"
            style={{ borderTop: '1px solid rgba(148,163,184,0.1)' }}
          />
          <div className="mb-2">
            <span
              className="text-[11px] font-semibold uppercase tracking-widest"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Son Aktivite
            </span>
          </div>
          <div className="flex gap-2 overflow-x-auto">
            {recentActivity.map((day) => {
              const d = new Date(day.day);
              const label = d.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' });
              return (
                <div
                  key={day.day}
                  className="flex min-w-[80px] flex-shrink-0 flex-col items-center gap-1 rounded-lg p-2"
                  style={{ background: 'rgba(15,23,42,0.5)' }}
                >
                  <span className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                    {label}
                  </span>
                  <span className="text-[13px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
                    {day.event_count}
                  </span>
                  <div className="flex gap-1.5 text-[9px]">
                    {(day.improved ?? 0) > 0 && (
                      <span style={{ color: '#34d399' }}>+{day.improved}</span>
                    )}
                    {(day.degraded ?? 0) > 0 && (
                      <span style={{ color: '#f87171' }}>-{day.degraded}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

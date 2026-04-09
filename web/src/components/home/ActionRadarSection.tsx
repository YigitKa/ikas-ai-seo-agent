import { useNavigate } from 'react-router-dom';
import { EnterpriseButton } from '../../shared/ui/EnterprisePrimitives';
import type { ActionCard } from './useHomeData';

interface ActionRadarSectionProps {
  actions: ActionCard[];
}

export default function ActionRadarSection({ actions }: ActionRadarSectionProps) {
  const navigate = useNavigate();

  if (actions.length === 0) return null;

  return (
    <div className="flex flex-col gap-3">
      {actions.map((card, idx) => (
        <div
          key={card.id}
          className="enterprise-surface rounded-2xl p-4 transition-all duration-300 hover:-translate-y-0.5"
          style={{
            background: 'linear-gradient(160deg, rgba(15,23,42,0.88), rgba(30,41,59,0.62))',
            border: '1px solid rgba(148,163,184,0.14)',
            animationDelay: `${idx * 100}ms`,
          }}
        >
          <div className="flex items-start gap-3">
            <div
              className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl"
              style={{
                background:
                  card.tone === 'success'
                    ? 'rgba(16,185,129,0.12)'
                    : card.tone === 'warning'
                      ? 'rgba(245,158,11,0.12)'
                      : card.tone === 'danger'
                        ? 'rgba(239,68,68,0.12)'
                        : 'rgba(99,102,241,0.12)',
                color:
                  card.tone === 'success'
                    ? '#34d399'
                    : card.tone === 'warning'
                      ? '#fbbf24'
                      : card.tone === 'danger'
                        ? '#f87171'
                        : '#a5b4fc',
              }}
            >
              <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d={card.icon} />
              </svg>
            </div>
            <div className="min-w-0 flex-1">
              <h3
                className="text-[15px] font-semibold leading-tight"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {card.title}
              </h3>
              <p className="mt-1 text-[13px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
                {card.description}
              </p>
            </div>
          </div>
          <div className="mt-3">
            <EnterpriseButton
              tone={card.tone}
              size="sm"
              fullWidth
              onClick={() => card.navigateTo && navigate(card.navigateTo)}
            >
              {card.cta}
            </EnterpriseButton>
          </div>
        </div>
      ))}
    </div>
  );
}

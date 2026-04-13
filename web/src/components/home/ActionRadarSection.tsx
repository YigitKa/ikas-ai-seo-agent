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
            background: 'linear-gradient(160deg, var(--surface-panel), var(--surface-raised))',
            border: '1px solid var(--color-divider)',
            animationDelay: `${idx * 100}ms`,
          }}
        >
          <div className="flex items-start gap-3">
            <div
              className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl"
              style={{
                background:
                  card.tone === 'success'
                    ? 'var(--tint-success-soft)'
                    : card.tone === 'warning'
                      ? 'var(--tint-warning-soft)'
                      : card.tone === 'danger'
                        ? 'var(--tint-danger-soft)'
                        : 'var(--tint-primary-soft)',
                color:
                  card.tone === 'success'
                    ? 'var(--color-icon-success)'
                    : card.tone === 'warning'
                      ? 'var(--color-icon-warning)'
                      : card.tone === 'danger'
                        ? 'var(--color-icon-danger)'
                        : 'var(--color-primary-light)',
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

import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { syncProductsFromIkas, analyzeAll } from '../../api/client';
import { EnterpriseButton } from '../../shared/ui/EnterprisePrimitives';
import { useToast } from '../../shared/ui/Toast';
import type { SettingsData, ReportSummary } from '../../types';

interface OnboardingFlowProps {
  settings?: SettingsData;
  summary?: ReportSummary;
}

interface Step {
  id: string;
  title: string;
  description: string;
  done: boolean;
  cta: string;
  action: () => void;
  isLoading?: boolean;
}

export default function OnboardingFlow({ settings, summary }: OnboardingFlowProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toasts = useToast();

  const syncMutation = useMutation({
    mutationFn: syncProductsFromIkas,
    onSuccess: (data) => {
      toasts.success(`${data.fetched_count} urun senkronize edildi.`);
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['report-summary'] });
    },
    onError: (err: Error) => {
      toasts.error(`Senkronizasyon basarisiz: ${err.message}`);
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: analyzeAll,
    onSuccess: () => {
      toasts.success('Analiz tamamlandi.');
      queryClient.invalidateQueries({ queryKey: ['report-summary'] });
      queryClient.invalidateQueries({ queryKey: ['score-distribution'] });
    },
    onError: (err: Error) => {
      toasts.error(`Analiz basarisiz: ${err.message}`);
    },
  });

  const hasConnection = !!(settings?.store_name && settings?.client_id);
  const hasProducts = (summary?.total_products ?? 0) > 0;
  const hasAI = !!(settings?.ai_provider && settings.ai_provider !== 'none');
  const hasAnalysis = (summary?.snapshot_count ?? 0) > 0;

  const steps: Step[] = [
    {
      id: 'connect',
      title: "ikas'a baglanin",
      description: 'Magaza adinizi ve API kimlik bilgilerinizi girin.',
      done: hasConnection,
      cta: 'Ayarlara Git',
      action: () => navigate('/settings'),
    },
    {
      id: 'sync',
      title: 'Urunleri senkronize edin',
      description: "ikas'tan urun katalogunuzu cekin.",
      done: hasProducts,
      cta: 'Senkronize Et',
      action: () => syncMutation.mutate(),
      isLoading: syncMutation.isPending,
    },
    {
      id: 'ai',
      title: 'AI motorunu yapilandirin',
      description: 'AI saglayicinizi ve modelinizi secin.',
      done: hasAI,
      cta: 'Ayarlara Git',
      action: () => navigate('/settings'),
    },
    {
      id: 'analyze',
      title: 'Ilk analizi baslatin',
      description: 'Tum urunlerinizin SEO skorlarini hesaplayin.',
      done: hasAnalysis,
      cta: 'Analiz Baslat',
      action: () => analyzeMutation.mutate(),
      isLoading: analyzeMutation.isPending,
    },
  ];

  const completedCount = steps.filter((s) => s.done).length;

  return (
    <div
      className="enterprise-surface mx-auto max-w-xl rounded-2xl p-6 sm:p-8"
      style={{
        background: 'linear-gradient(160deg, rgba(15,23,42,0.92), rgba(30,41,59,0.72))',
        border: '1px solid rgba(148,163,184,0.14)',
      }}
    >
      {/* Header */}
      <div className="mb-6 text-center">
        <div
          className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl"
          style={{
            background: 'linear-gradient(135deg, #0f172a, #1d4ed8)',
            border: '1px solid rgba(96,165,250,0.34)',
            boxShadow: '0 18px 36px rgba(29,78,216,0.22)',
          }}
        >
          <span className="text-lg font-bold text-white">AI</span>
        </div>
        <h2 className="mt-4 text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
          Hosgeldiniz!
        </h2>
        <p className="mt-1.5 text-[13px]" style={{ color: 'var(--color-text-secondary)' }}>
          Magazanizin SEO komuta merkezini kurmak icin asagidaki adimlari tamamlayin.
        </p>
        {/* Progress */}
        <div className="mx-auto mt-4 flex max-w-xs items-center gap-2">
          {steps.map((step) => (
            <div
              key={step.id}
              className="h-1.5 flex-1 rounded-full transition-all duration-500"
              style={{
                background: step.done
                  ? 'linear-gradient(90deg, #10b981, #06b6d4)'
                  : 'rgba(148,163,184,0.15)',
              }}
            />
          ))}
          <span className="ml-1 text-[11px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
            {completedCount}/{steps.length}
          </span>
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {steps.map((step, idx) => (
          <div
            key={step.id}
            className="flex items-center gap-4 rounded-xl p-3.5 transition-all duration-200"
            style={{
              background: step.done ? 'rgba(16,185,129,0.06)' : 'rgba(15,23,42,0.5)',
              border: step.done
                ? '1px solid rgba(16,185,129,0.2)'
                : '1px solid rgba(148,163,184,0.1)',
            }}
          >
            {/* Checkbox */}
            <div
              className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full"
              style={{
                background: step.done ? 'rgba(16,185,129,0.15)' : 'rgba(148,163,184,0.1)',
                color: step.done ? '#34d399' : 'var(--color-text-muted)',
              }}
            >
              {step.done ? (
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <span className="text-[11px] font-bold">{idx + 1}</span>
              )}
            </div>

            {/* Content */}
            <div className="min-w-0 flex-1">
              <div
                className="text-[13px] font-medium"
                style={{ color: step.done ? '#34d399' : 'var(--color-text-primary)' }}
              >
                {step.title}
              </div>
              <div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                {step.description}
              </div>
            </div>

            {/* CTA */}
            {!step.done && (
              <EnterpriseButton
                size="sm"
                tone="primary"
                onClick={step.action}
                disabled={step.isLoading}
              >
                {step.isLoading ? 'Isleniyor...' : step.cta}
              </EnterpriseButton>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

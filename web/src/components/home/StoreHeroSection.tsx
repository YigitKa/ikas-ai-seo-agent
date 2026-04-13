import { useNavigate } from 'react-router-dom';
import CircularScore from '../../shared/ui/CircularScore';
import { EnterprisePill } from '../../shared/ui/EnterprisePrimitives';
import type { ReportSummary, SettingsData } from '../../types';

interface StoreHeroSectionProps {
  settings?: SettingsData;
  summary?: ReportSummary;
  isLoading: boolean;
}

export default function StoreHeroSection({ settings, summary, isLoading }: StoreHeroSectionProps) {
  const navigate = useNavigate();

  const storeName = settings?.store_name || 'Magaza';
  const provider = settings?.ai_provider || '';
  const model = settings?.ai_model_name || '';
  const langStr = settings?.languages || 'tr';
  const languages = langStr.split(',').map((l: string) => l.trim()).filter(Boolean);
  const totalScore = Math.round(summary?.latest_avg?.total ?? 0);
  const delta = summary?.improvement?.total ?? 0;
  const daysTracked = summary?.days_tracked ?? 0;
  const totalProducts = summary?.total_products ?? 0;

  if (isLoading) {
    return (
      <section
        className="enterprise-surface animate-pulse rounded-2xl p-6"
        style={{ minHeight: 140 }}
      />
    );
  }

  return (
    <section
      className="enterprise-surface rounded-2xl p-5 sm:p-6"
      style={{
        background: 'linear-gradient(135deg, var(--surface-panel), var(--surface-raised))',
        border: '1px solid var(--color-divider)',
      }}
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        {/* Left — Store identity */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {languages.map((lang: string) => (
              <EnterprisePill key={lang} tone="neutral" className="text-[9px]">
                {lang.toUpperCase()}
              </EnterprisePill>
            ))}
            {daysTracked > 0 && (
              <EnterprisePill tone="primary" className="text-[9px]">
                {daysTracked} gun takip
              </EnterprisePill>
            )}
          </div>

          <h1
            className="mt-3 text-xl font-bold tracking-tight sm:text-2xl"
            style={{ color: 'var(--color-text-primary)' }}
          >
            {storeName} SEO Komuta Merkezi
          </h1>

          <p className="mt-1.5 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
            {provider && model
              ? `AI motoru: ${provider} / ${model}`
              : 'AI motoru yapilandirilmadi'}
            {totalProducts > 0 && ` \u2022 ${totalProducts} urun`}
          </p>
        </div>

        {/* Right — Health ring + delta */}
        <div
          className="flex flex-shrink-0 cursor-pointer items-center gap-4"
          onClick={() => navigate('/reports')}
          title="Detayli raporlara git"
        >
          <CircularScore score={totalScore} size={120} animated delay={200} subtitle="/100" />

          {delta !== 0 && daysTracked > 0 && (
            <div className="flex flex-col items-center gap-1">
              <span
                className="rounded-full px-2.5 py-1 text-xs font-bold"
                style={{
                  background: delta > 0 ? 'var(--tint-success-soft)' : 'var(--tint-danger-soft)',
                  color: delta > 0 ? 'var(--color-icon-success)' : 'var(--color-icon-danger)',
                  border: delta > 0
                    ? '1px solid var(--color-border-success)'
                    : '1px solid var(--color-border-danger)',
                }}
              >
                {delta > 0 ? '+' : ''}{delta.toFixed(1)}
              </span>
              <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                puan
              </span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

import { useQuery } from '@tanstack/react-query';
import type { BatchConfig } from '../../types';
import { getCategories } from '../../api/client';

const FIELD_OPTIONS: { key: string; label: string }[] = [
  { key: 'meta_title', label: 'Meta Baslik' },
  { key: 'meta_description', label: 'Meta Aciklama' },
  { key: 'name', label: 'Urun Basligi' },
  { key: 'description', label: 'Aciklama (TR)' },
  { key: 'description_en', label: 'Aciklama (EN)' },
];

interface Props {
  config: BatchConfig;
  onChange: (config: BatchConfig) => void;
  onStartCalibration: () => void;
  onStartDirect: () => void;
  disabled: boolean;
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
          {label}
        </p>
        <p className="mt-0.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          {description}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className="relative mt-0.5 h-5 w-9 flex-shrink-0 rounded-full transition-colors"
        style={{
          background: checked ? 'var(--color-primary)' : 'rgba(255,255,255,0.12)',
        }}
      >
        <span
          className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform"
          style={{ left: checked ? '18px' : '2px' }}
        />
      </button>
    </div>
  );
}

export default function BatchConfigPanel({
  config,
  onChange,
  onStartCalibration,
  onStartDirect,
  disabled,
}: Props) {
  const set = <K extends keyof BatchConfig>(key: K, value: BatchConfig[K]) =>
    onChange({ ...config, [key]: value });

  const { data: categories = [] } = useQuery({
    queryKey: ['productCategories'],
    queryFn: getCategories,
    staleTime: 60_000,
  });

  const toggleField = (field: string) => {
    const current = config.target_fields ?? FIELD_OPTIONS.map((option) => option.key);
    const next = current.includes(field)
      ? current.filter((item) => item !== field)
      : [...current, field];

    if (next.length > 0) {
      set('target_fields', next);
    }
  };

  const isDryRun = true;

  return (
    <div
      className="rounded-xl p-5"
      style={{
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
      }}
    >
      <h3
        className="mb-4 text-[13px] font-semibold uppercase tracking-wider"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Konfigurasyon
      </h3>

      <div className="space-y-5">
        <section>
          <p
            className="mb-3 text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-primary-light)' }}
          >
            Hedefleme Filtreleri
          </p>
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <label
                className="w-40 flex-shrink-0 text-[12px]"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                SEO Esigi (max skor)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={config.score_threshold}
                onChange={(event) => set('score_threshold', Number(event.target.value))}
                disabled={disabled}
                className="w-20 rounded-lg px-2.5 py-1.5 text-center text-[13px] outline-none disabled:opacity-40"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              />
              <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                puan altindaki urunler
              </span>
            </div>

            <div className="flex items-center gap-3">
              <label
                className="w-40 flex-shrink-0 text-[12px]"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Kategori Filtresi
              </label>
              <select
                value={config.category_filter}
                onChange={(event) => set('category_filter', event.target.value)}
                disabled={disabled}
                className="flex-1 rounded-lg px-2.5 py-1.5 text-[13px] outline-none disabled:opacity-40"
                style={{
                  background: '#1e1e2e',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              >
                <option value="" style={{ background: '#1e1e2e', color: 'var(--color-text-primary)' }}>
                  Tum Kategoriler
                </option>
                {categories.map((category) => (
                  <option
                    key={category}
                    value={category}
                    style={{ background: '#1e1e2e', color: 'var(--color-text-primary)' }}
                  >
                    {category}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section>
          <p
            className="mb-2 text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-primary-light)' }}
          >
            Guncellenecek Alanlar
          </p>
          <p className="mb-3 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
            AI yalnizca secili alanlari degistirecek, digerlerine dokunmayacak.
          </p>
          <div className="flex flex-wrap gap-2">
            {FIELD_OPTIONS.map((field) => {
              const active = (config.target_fields ?? FIELD_OPTIONS.map((option) => option.key)).includes(field.key);

              return (
                <button
                  key={field.key}
                  type="button"
                  onClick={() => toggleField(field.key)}
                  disabled={disabled}
                  className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all disabled:opacity-40"
                  style={{
                    background: active ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.04)',
                    border: active ? '1px solid rgba(99,102,241,0.5)' : '1px solid var(--color-border)',
                    color: active ? 'var(--color-primary-light)' : 'var(--color-text-muted)',
                  }}
                >
                  {active && (
                    <svg className="mr-1 -ml-0.5 inline h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {field.label}
                </button>
              );
            })}
          </div>
        </section>

        <section>
          <p
            className="mb-3 text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-primary-light)' }}
          >
            Operasyonel Kisitalar
          </p>
          <div className="space-y-4">
            <Toggle
              label="Teknik Veri Koruma"
              description="Materyal, boyut ve agirlik gibi teknik ozellikleri koru; yalnizca dili duzenle."
              checked={config.preserve_specs}
              onChange={(value) => set('preserve_specs', value)}
            />
            <Toggle
              label="Kanibalizasyon Onleme"
              description="Ayni kategorideki urunlerin ayni sorgular icin birbirini ezmesini azalt."
              checked={config.prevent_cannibalization}
              onChange={(value) => set('prevent_cannibalization', value)}
            />
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <p className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  Maks. Baslik Degisimi
                </p>
                <span
                  className="rounded px-1.5 py-0.5 text-[12px] font-semibold tabular-nums"
                  style={{
                    background: 'rgba(99,102,241,0.15)',
                    color: 'var(--color-primary-light)',
                  }}
                >
                  %{config.max_title_change_pct}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={config.max_title_change_pct}
                onChange={(event) => set('max_title_change_pct', Number(event.target.value))}
                disabled={disabled}
                className="w-full accent-indigo-500 disabled:opacity-40"
              />
              <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                <span>Minimal (%0)</span>
                <span>Tam Ozgurluk (%100)</span>
              </div>
            </div>
          </div>
        </section>

        <div
          className="flex items-start gap-3 rounded-lg px-4 py-3"
          style={{
            background: 'rgba(245,158,11,0.08)',
            border: '1px solid rgba(245,158,11,0.25)',
          }}
        >
          <svg className="mt-0.5 h-5 w-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="text-[12px] font-semibold" style={{ color: '#f59e0b' }}>
              {isDryRun ? 'Guvenli Mod (DRY_RUN) Aktif' : 'DIKKAT: Canli Mod'}
            </p>
            <p className="mt-0.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {isDryRun
                ? 'Degisiklikler yalnizca taslak olarak kaydedilecek, magazaniza yazilmayacak.'
                : 'Degisiklikler dogrudan magazaniza uygulanacak.'}
            </p>
          </div>
        </div>

        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={onStartCalibration}
            disabled={disabled || config.target_fields.length === 0}
            className="flex-1 rounded-lg px-4 py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            Kalibrasyon Baslat
          </button>
          <button
            type="button"
            onClick={onStartDirect}
            disabled={disabled || config.target_fields.length === 0}
            className="rounded-lg px-4 py-2 text-[13px] font-medium transition-colors hover:bg-[var(--color-bg-hover)] disabled:opacity-40"
            style={{
              border: '1px solid var(--color-border-light)',
              color: 'var(--color-text-secondary)',
            }}
          >
            Direkt Calistir
          </button>
        </div>
      </div>
    </div>
  );
}

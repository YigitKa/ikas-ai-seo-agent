import type { BatchConfig } from '../../types';

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
  onChange: (v: boolean) => void;
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
        Konfigürasyon
      </h3>

      <div className="space-y-5">
        {/* Targeting */}
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
                SEO Eşiği (max skor)
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={config.score_threshold}
                onChange={(e) => set('score_threshold', Number(e.target.value))}
                disabled={disabled}
                className="w-20 rounded-lg px-2.5 py-1.5 text-center text-[13px] outline-none disabled:opacity-40"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              />
              <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                puan altındaki ürünler
              </span>
            </div>

            <div className="flex items-center gap-3">
              <label
                className="w-40 flex-shrink-0 text-[12px]"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Kategori Filtresi
              </label>
              <input
                type="text"
                value={config.category_filter}
                onChange={(e) => set('category_filter', e.target.value)}
                disabled={disabled}
                placeholder="Boş = tümü"
                className="flex-1 rounded-lg px-2.5 py-1.5 text-[13px] outline-none placeholder:opacity-40 disabled:opacity-40"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              />
            </div>

            <div className="flex items-center gap-3">
              <label
                className="w-40 flex-shrink-0 text-[12px]"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Örneklem Boyutu
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={config.sample_size}
                onChange={(e) => set('sample_size', Number(e.target.value))}
                disabled={disabled}
                className="w-20 rounded-lg px-2.5 py-1.5 text-center text-[13px] outline-none disabled:opacity-40"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              />
              <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                kalibrasyon ürünü
              </span>
            </div>
          </div>
        </section>

        {/* Constraints */}
        <section>
          <p
            className="mb-3 text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-primary-light)' }}
          >
            Operasyonel Kısıtlamalar
          </p>
          <div className="space-y-4">
            <Toggle
              label="Teknik Veri Koruma"
              description="Materyal, boyut, ağırlık gibi teknik özellikleri değiştirme; sadece biçimlendir."
              checked={config.preserve_specs}
              onChange={(v) => set('preserve_specs', v)}
            />
            <Toggle
              label="Kanibalizasyon Önleme"
              description="Benzer ürün gruplarında LSI varyasyonları kullan, anahtar kelime çakışmasını önle."
              checked={config.prevent_cannibalization}
              onChange={(v) => set('prevent_cannibalization', v)}
            />
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <p className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  Maks. Başlık Değişimi
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
                onChange={(e) => set('max_title_change_pct', Number(e.target.value))}
                disabled={disabled}
                className="w-full accent-indigo-500 disabled:opacity-40"
              />
              <div className="flex justify-between text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                <span>Minimal (%0)</span>
                <span>Tam Özgürlük (%100)</span>
              </div>
            </div>
          </div>
        </section>

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={onStartCalibration}
            disabled={disabled}
            className="flex-1 rounded-lg px-4 py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            Kalibrasyon Başlat
          </button>
          <button
            type="button"
            onClick={onStartDirect}
            disabled={disabled}
            className="rounded-lg px-4 py-2 text-[13px] font-medium transition-colors hover:bg-[var(--color-bg-hover)] disabled:opacity-40"
            style={{
              border: '1px solid var(--color-border-light)',
              color: 'var(--color-text-secondary)',
            }}
          >
            Direkt Çalıştır
          </button>
        </div>
      </div>
    </div>
  );
}

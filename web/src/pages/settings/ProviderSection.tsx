import { Field, SectionCard, SelectField } from '../../components/settings/UiPrimitives';
import type { ProviderInfo, SettingsData } from '../../types';
import type { ProviderMeta } from './constants';

interface ProviderSectionProps {
  form: SettingsData;
  setValue: <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => void;
  currentProvider: string;
  providerMeta: ProviderMeta;
  providerOptions: ProviderInfo[];
  modelOptions: string[];
  showApiKey: boolean;
  showBaseUrl: boolean;
  useModelSelect: boolean;
  canDiscoverModels: boolean;
  onProviderChange: (provider: string) => void;
  onModelDiscovery: () => void;
  isDiscovering: boolean;
  providerError: Error | null;
}

export default function ProviderSection({
  form,
  setValue,
  currentProvider,
  providerMeta,
  providerOptions,
  modelOptions,
  showApiKey,
  showBaseUrl,
  useModelSelect,
  canDiscoverModels,
  onProviderChange,
  onModelDiscovery,
  isDiscovering,
  providerError,
}: ProviderSectionProps) {
  return (
    <SectionCard
      eyebrow="AI"
      title="Provider ve Model"
      description={providerMeta.summary}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <SelectField
            label="Provider"
            value={currentProvider}
            onChange={onProviderChange}
            options={providerOptions.map((provider) => ({
              value: provider.key,
              label: provider.label,
            }))}
          />
        </div>

        {showApiKey && (
          <Field
            label={providerMeta.apiKeyLabel || 'API Key'}
            value={form.ai_api_key}
            onChange={(value) => setValue('ai_api_key', value)}
            type="password"
            placeholder={providerMeta.apiKeyPlaceholder}
          />
        )}

        {showBaseUrl && (
          <Field
            label={providerMeta.baseUrlLabel || 'Base URL'}
            value={providerMeta.lockedBaseUrl || form.ai_base_url}
            onChange={(value) => setValue('ai_base_url', value)}
            placeholder={providerMeta.baseUrlPlaceholder}
            disabled={Boolean(providerMeta.lockedBaseUrl)}
            hint={providerMeta.lockedBaseUrl ? 'Bu provider icin sabit endpoint kullanilir.' : undefined}
          />
        )}

        <Field
          label="Temperature"
          value={String(form.ai_temperature)}
          onChange={(value) => setValue('ai_temperature', Number.parseFloat(value) || 0.7)}
          placeholder="0.7"
        />
        <Field
          label="Max Tokens"
          value={String(form.ai_max_tokens)}
          onChange={(value) => setValue('ai_max_tokens', Number.parseInt(value, 10) || 2000)}
          placeholder="2000"
        />

        <div className="md:col-span-2">
          {useModelSelect ? (
            <SelectField
              label="Model"
              value={form.ai_model_name}
              onChange={(value) => setValue('ai_model_name', value)}
              options={modelOptions.map((model) => ({ value: model, label: model }))}
              hint={providerMeta.modelHint}
            />
          ) : (
            <Field
              label="Model"
              value={form.ai_model_name}
              onChange={(value) => setValue('ai_model_name', value)}
              placeholder="Model adini girin"
              hint={providerMeta.modelHint}
            />
          )}
        </div>
      </div>

      {canDiscoverModels && (
        <div className="mt-5 flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-950/70 p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-medium text-white">Yerel model tarama</div>
            <p className="mt-1 text-sm text-slate-400">
              Base URL uzerinden kurulu modelleri okuyup dropdown'u doldurur.
            </p>
          </div>
          <button
            onClick={onModelDiscovery}
            disabled={isDiscovering}
            className="inline-flex h-11 items-center justify-center rounded-2xl border border-sky-500/40 bg-sky-500/10 px-4 text-sm font-medium text-sky-200 transition hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDiscovering ? 'Taraniyor...' : 'Modelleri Tara'}
          </button>
        </div>
      )}

      {providerError && (
        <p className="mt-4 text-sm text-amber-300">
          Provider listesi API'den alinamadi. Mevcut secim korunuyor.
        </p>
      )}
    </SectionCard>
  );
}

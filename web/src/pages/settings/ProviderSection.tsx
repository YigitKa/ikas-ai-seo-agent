import {
  EnterpriseButton,
  EnterpriseField,
  EnterpriseSectionCard,
  EnterpriseSelectField,
} from '../../shared/ui/EnterprisePrimitives';
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
    <EnterpriseSectionCard
      eyebrow="AI"
      title="Provider ve Model"
      description={providerMeta.summary}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <EnterpriseSelectField
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
          <EnterpriseField
            label={providerMeta.apiKeyLabel || 'API Key'}
            value={form.ai_api_key}
            onChange={(value) => setValue('ai_api_key', value)}
            type="password"
            placeholder={providerMeta.apiKeyPlaceholder}
          />
        )}

        {showBaseUrl && (
          <EnterpriseField
            label={providerMeta.baseUrlLabel || 'Base URL'}
            value={providerMeta.lockedBaseUrl || form.ai_base_url}
            onChange={(value) => setValue('ai_base_url', value)}
            placeholder={providerMeta.baseUrlPlaceholder}
            disabled={Boolean(providerMeta.lockedBaseUrl)}
            hint={providerMeta.lockedBaseUrl ? 'Bu provider icin sabit endpoint kullanilir.' : undefined}
          />
        )}

        <EnterpriseField
          label="Temperature"
          value={String(form.ai_temperature)}
          onChange={(value) => setValue('ai_temperature', Number.parseFloat(value) || 0.7)}
          placeholder="0.7"
        />
        <EnterpriseField
          label="Max Tokens"
          value={String(form.ai_max_tokens)}
          onChange={(value) => setValue('ai_max_tokens', Number.parseInt(value, 10) || 2000)}
          placeholder="2000"
        />

        <div className="md:col-span-2">
          {useModelSelect ? (
            <EnterpriseSelectField
              label="Model"
              value={form.ai_model_name}
              onChange={(value) => setValue('ai_model_name', value)}
              options={modelOptions.map((model) => ({ value: model, label: model }))}
              hint={providerMeta.modelHint}
            />
          ) : (
            <EnterpriseField
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
        <div
          className="enterprise-list-item mt-5 flex flex-col gap-3 rounded-xl p-4 transition-all duration-200 md:flex-row md:items-center md:justify-between"
        >
          <div>
            <div className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              Yerel model tarama
            </div>
            <p className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              Base URL uzerinden kurulu modelleri okuyup dropdown'u doldurur.
            </p>
          </div>
          <EnterpriseButton
            onClick={onModelDiscovery}
            disabled={isDiscovering}
            tone="primary"
            size="lg"
          >
            {isDiscovering ? 'Taraniyor...' : 'Modelleri Tara'}
          </EnterpriseButton>
        </div>
      )}

      {providerError && (
        <p className="mt-4 text-[13px]" style={{ color: 'var(--color-warning)' }}>
          Provider listesi API'den alinamadi. Mevcut secim korunuyor.
        </p>
      )}
    </EnterpriseSectionCard>
  );
}

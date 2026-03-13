import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getMcpStatus,
  getLmStudioLiveStatus,
  getPromptTemplates,
  getProviderHealth,
  getProviderModels,
  getProviders,
  getSettings,
  initializeMcp,
  resetPromptTemplates,
  savePromptTemplates,
  testConnection,
  updateSettings,
} from '../api/client';
import type { PromptGroup, SettingsData } from '../types';
import { Banner, Field, PromptCard, SectionCard, SelectField, StatusPill, StatusRow, ToggleField, type BannerTone } from '../components/settings/UiPrimitives';

type BannerState = {
  tone: BannerTone;
  message: string;
} | null;

type ProviderMeta = {
  summary: string;
  apiKeyLabel?: string;
  apiKeyPlaceholder?: string;
  baseUrlLabel?: string;
  baseUrlPlaceholder?: string;
  defaultBaseUrl?: string;
  lockedBaseUrl?: string;
  modelHint: string;
};

const PROVIDER_META: Record<string, ProviderMeta> = {
  none: {
    summary: 'AI yeniden yazma kapali. Sadece SEO analizi calisir.',
    modelHint: 'Model secimi gerekmiyor.',
  },
  anthropic: {
    summary: 'Claude modelleri ile urun rewrite ve ceviri uretir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'sk-ant-...',
    modelHint: 'Hazir Claude modellerinden birini secin.',
  },
  openai: {
    summary: 'OpenAI Responses/Chat uyumlu endpoint kullanir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'sk-...',
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://api.openai.com/v1',
    defaultBaseUrl: 'https://api.openai.com/v1',
    modelHint: 'Hazir GPT modelleri listelenir.',
  },
  gemini: {
    summary: 'Google Gemini API ile rewrite ve translation calisir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'AIza...',
    modelHint: 'Gemini modelini secin.',
  },
  openrouter: {
    summary: 'OpenRouter ile tek API key uzerinden farkli saglayicilari kullanir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'sk-or-...',
    baseUrlLabel: 'Base URL',
    lockedBaseUrl: 'https://openrouter.ai/api/v1',
    modelHint: 'Saglayici/model formatinda model secin.',
  },
  ollama: {
    summary: 'Yerel Ollama instance uzerinden calisir. Model listesini tarayabilirsiniz.',
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'http://localhost:11434/v1',
    defaultBaseUrl: 'http://localhost:11434/v1',
    modelHint: 'Kurulu modelleri tarayin ya da elle model girin.',
  },
  'lm-studio': {
    summary: 'Yerel LM Studio OpenAI-compatible endpoint kullanir.',
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'http://localhost:1234/v1',
    defaultBaseUrl: 'http://localhost:1234/v1',
    modelHint: 'Yuklu modelleri tarayin ya da elle model girin.',
  },
  custom: {
    summary: 'OpenAI-compatible herhangi bir endpoint ile calisir.',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'Opsiyonel',
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://your-endpoint.example/v1',
    modelHint: 'Model adini manuel girin.',
  },
};

const PRESET_MODELS: Record<string, string[]> = {
  anthropic: [
    'claude-haiku-4-5-20251001',
    'claude-sonnet-4-5-20250514',
    'claude-opus-4-5-20250514',
    'claude-haiku-3-5-20241022',
  ],
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  gemini: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash'],
  openrouter: [
    'openai/gpt-4o-mini',
    'openai/gpt-4o',
    'anthropic/claude-3-haiku',
    'anthropic/claude-3-sonnet',
    'google/gemini-flash-1.5',
    'meta-llama/llama-3-8b-instruct',
  ],
};

const DISCOVERABLE_PROVIDERS = new Set(['ollama', 'lm-studio']);

export default function Settings() {
  const qc = useQueryClient();
  const [form, setForm] = useState<SettingsData | null>(null);
  const [promptGroups, setPromptGroups] = useState<PromptGroup[]>([]);
  const [promptValues, setPromptValues] = useState<Record<string, string>>({});
  const [activePromptGroup, setActivePromptGroup] = useState('');
  const [discoveredModels, setDiscoveredModels] = useState<Record<string, string[]>>({});
  const [banner, setBanner] = useState<BannerState>(null);
  const [downloadJobId, setDownloadJobId] = useState('');

  const settingsQ = useQuery({ queryKey: ['settings'], queryFn: getSettings });
  const promptsQ = useQuery({ queryKey: ['prompt-templates'], queryFn: getPromptTemplates });
  const providersQ = useQuery({ queryKey: ['providers'], queryFn: getProviders });
  const healthQ = useQuery({ queryKey: ['provider-health'], queryFn: getProviderHealth });
  const mcpQ = useQuery({ queryKey: ['mcp-status'], queryFn: getMcpStatus });
  const activeProvider = form?.ai_provider || settingsQ.data?.ai_provider || 'none';
  const lmStudioLiveQ = useQuery({
    queryKey: ['lm-studio-live-status', activeProvider, downloadJobId],
    queryFn: () => getLmStudioLiveStatus(downloadJobId.trim()),
    enabled: activeProvider === 'lm-studio',
    staleTime: 2_000,
    refetchInterval: activeProvider === 'lm-studio' ? 2_500 : false,
  });

  useEffect(() => {
    if (settingsQ.data) {
      setForm((prev) => prev ?? settingsQ.data);
    }
  }, [settingsQ.data]);

  useEffect(() => {
    if (!promptsQ.data || promptGroups.length > 0) {
      return;
    }
    syncPromptGroups(promptsQ.data.groups);
  }, [promptGroups.length, promptsQ.data]);

  useEffect(() => {
    if (!form) {
      return;
    }

    const provider = form.ai_provider || 'none';
    const meta = PROVIDER_META[provider] ?? PROVIDER_META.none;
    const fallbackModel = buildModelOptions(provider, '', discoveredModels[provider] ?? [])[0] ?? '';

    setForm((prev) => {
      if (!prev || prev.ai_provider !== provider) {
        return prev;
      }

      let changed = false;
      let next = prev;

      if (meta.lockedBaseUrl && prev.ai_base_url !== meta.lockedBaseUrl) {
        next = { ...next, ai_base_url: meta.lockedBaseUrl };
        changed = true;
      } else if (!prev.ai_base_url && meta.defaultBaseUrl) {
        next = { ...next, ai_base_url: meta.defaultBaseUrl };
        changed = true;
      }

      if (!prev.ai_model_name && fallbackModel) {
        next = { ...next, ai_model_name: fallbackModel };
        changed = true;
      }

      return changed ? next : prev;
    });
  }, [discoveredModels, form]);

  const saveAllMut = useMutation({
    mutationFn: async (payload: { settings: SettingsData; prompts: Record<string, string> }) => {
      await savePromptTemplates(payload.prompts);
      return updateSettings(payload.settings as unknown as Record<string, unknown>);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] });
      qc.invalidateQueries({ queryKey: ['prompt-templates'] });
      qc.invalidateQueries({ queryKey: ['provider-health'] });
      qc.invalidateQueries({ queryKey: ['mcp-status'] });
      setBanner({ tone: 'success', message: 'Ayarlar ve promptlar kaydedildi.' });
    },
    onError: (error) => {
      setBanner({ tone: 'error', message: formatError(error, 'Kaydetme sirasinda hata olustu.') });
    },
  });

  const resetPromptMut = useMutation({
    mutationFn: (promptKeys: string[]) => resetPromptTemplates(promptKeys),
    onSuccess: (data, promptKeys) => {
      syncPromptGroups(data.groups);
      qc.invalidateQueries({ queryKey: ['prompt-templates'] });
      setBanner({
        tone: 'success',
        message:
          promptKeys.length === 1
            ? 'Prompt varsayilan haline donduruldu.'
            : 'Tum promptlar varsayilan haline donduruldu.',
      });
    },
    onError: (error) => {
      setBanner({ tone: 'error', message: formatError(error, 'Prompt sifirlama basarisiz oldu.') });
    },
  });

  const testMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => testConnection(values),
    onError: (error) => {
      setBanner({ tone: 'error', message: formatError(error, 'Baglanti testi calismadi.') });
    },
  });

  const mcpInitMut = useMutation({
    mutationFn: () => initializeMcp(),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['mcp-status'] });
      setBanner({
        tone: result.initialized ? 'success' : 'error',
        message: result.message || 'MCP durumu guncellendi.',
      });
    },
    onError: (error) => {
      setBanner({ tone: 'error', message: formatError(error, 'MCP baglantisi kurulamadi.') });
    },
  });

  const discoverModelsMut = useMutation({
    mutationFn: async ({ provider, baseUrl }: { provider: string; baseUrl: string }) => {
      const result = await getProviderModels(provider, baseUrl);
      return { provider, models: result.models };
    },
    onSuccess: ({ provider, models }) => {
      setDiscoveredModels((prev) => ({ ...prev, [provider]: models }));
      setForm((prev) => {
        if (!prev || prev.ai_provider !== provider) {
          return prev;
        }
        if (prev.ai_model_name && models.includes(prev.ai_model_name)) {
          return prev;
        }
        if (!models[0]) {
          return prev;
        }
        return { ...prev, ai_model_name: models[0] };
      });
      setBanner({
        tone: models.length > 0 ? 'success' : 'info',
        message: models.length > 0 ? `${models.length} model bulundu.` : 'Baglanti kuruldu ama model listesi bos dondu.',
      });
    },
    onError: (error) => {
      setBanner({ tone: 'error', message: formatError(error, 'Model listesi alinamadi.') });
    },
  });

  if ((settingsQ.isLoading && !form) || (promptsQ.isLoading && promptGroups.length === 0)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-300">
        Ayar arayuzu yukleniyor...
      </div>
    );
  }

  if (!form) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-center text-slate-300">
        {formatError(settingsQ.error, 'Ayarlar okunamadi.')}
      </div>
    );
  }

  const currentProvider = form.ai_provider || 'none';
  const providerMeta = PROVIDER_META[currentProvider] ?? PROVIDER_META.none;
  const providerOptions =
    providersQ.data?.providers?.length
      ? providersQ.data.providers
      : [{ key: currentProvider, label: currentProvider }];
  const availablePromptGroups = promptGroups.length > 0 ? promptGroups : promptsQ.data?.groups ?? [];
  const selectedPromptGroup =
    availablePromptGroups.find((group) => group.label === activePromptGroup) ??
    availablePromptGroups[0];
  const modelOptions = buildModelOptions(
    currentProvider,
    form.ai_model_name,
    discoveredModels[currentProvider] ?? [],
  );
  const showApiKey = !['none', 'ollama', 'lm-studio'].includes(currentProvider);
  const showBaseUrl = ['openai', 'openrouter', 'ollama', 'lm-studio', 'custom'].includes(
    currentProvider,
  );
  const useModelSelect = currentProvider !== 'custom' && modelOptions.length > 0;
  const canDiscoverModels = DISCOVERABLE_PROVIDERS.has(currentProvider);
  const promptCount = availablePromptGroups.reduce((total, group) => total + group.prompts.length, 0);

  const setValue = <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const handleProviderChange = (nextProvider: string) => {
    const meta = PROVIDER_META[nextProvider] ?? PROVIDER_META.none;
    setForm((prev) => {
      if (!prev) {
        return prev;
      }
      const nextModel =
        prev.ai_model_name || PRESET_MODELS[nextProvider]?.[0] || discoveredModels[nextProvider]?.[0] || '';
      let nextBaseUrl = prev.ai_base_url;
      if (meta.lockedBaseUrl) {
        nextBaseUrl = meta.lockedBaseUrl;
      } else if (!nextBaseUrl && meta.defaultBaseUrl) {
        nextBaseUrl = meta.defaultBaseUrl;
      }
      return {
        ...prev,
        ai_provider: nextProvider,
        ai_base_url: nextBaseUrl,
        ai_model_name: nextModel,
      };
    });
  };

  const handleSaveAll = () => {
    setBanner(null);
    saveAllMut.mutate({ settings: form, prompts: promptValues });
  };

  const handleConnectionTest = () => {
    setBanner(null);
    testMut.mutate(form as unknown as Record<string, unknown>);
  };

  const handlePromptChange = (promptKey: string, value: string) => {
    setPromptValues((prev) => ({ ...prev, [promptKey]: value }));
  };

  const handlePromptReset = (promptKey: string) => {
    setBanner(null);
    resetPromptMut.mutate([promptKey]);
  };

  const handleResetAllPrompts = () => {
    setBanner(null);
    resetPromptMut.mutate([]);
  };

  const handleModelDiscovery = () => {
    setBanner(null);
    discoverModelsMut.mutate({
      provider: currentProvider,
      baseUrl: form.ai_base_url,
    });
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(37,99,235,0.25),_transparent_32%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.18),_transparent_24%),linear-gradient(180deg,_#020617,_#0f172a_42%,_#020617)] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-col gap-4 rounded-3xl border border-slate-800/80 bg-slate-950/65 p-6 shadow-2xl shadow-slate-950/40 backdrop-blur md:flex-row md:items-end md:justify-between">
          <div className="space-y-3">
            <Link to="/" className="inline-flex text-sm text-sky-300 transition hover:text-sky-200">
              &larr; Dashboard
            </Link>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-white">Ayar Merkezi</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                AI provider, ikas baglantisi, SEO ayarlari ve prompt dosyalari tek ekrandan
                yonetilir. Prompt degisiklikleri bir sonraki AI isteginde aktif olur.
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatusPill
              label="Provider"
              value={healthQ.data?.message || currentProvider}
              tone={toneFromHealth(healthQ.data?.status)}
            />
            <StatusPill
              label="MCP"
              value={mcpQ.data?.message || 'Durum okunuyor'}
              tone={mcpQ.data?.initialized ? 'success' : 'info'}
            />
            <StatusPill
              label="Prompt"
              value={`${promptCount} dosya aktif`}
              tone="info"
            />
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <SectionCard
              eyebrow="ikas"
              title="Magaza ve SEO Ayarlari"
              description="Magaza baglantisi ve rewrite islerinde kullanilan genel hedefler."
            >
              <div className="grid gap-4 md:grid-cols-2">
                <Field
                  label="Magaza Adi"
                  value={form.store_name}
                  onChange={(value) => setValue('store_name', value)}
                  placeholder="my-store"
                />
                <Field
                  label="Client ID"
                  value={form.client_id}
                  onChange={(value) => setValue('client_id', value)}
                  placeholder="ikas oauth client id"
                />
                <Field
                  label="Client Secret"
                  value={form.client_secret}
                  onChange={(value) => setValue('client_secret', value)}
                  type="password"
                  placeholder="ikas oauth client secret"
                />
                <Field
                  label="MCP Token"
                  value={form.mcp_token}
                  onChange={(value) => setValue('mcp_token', value)}
                  type="password"
                  placeholder="mcp_..."
                />
                <Field
                  label="Magaza Dilleri"
                  value={form.languages}
                  onChange={(value) => setValue('languages', value)}
                  placeholder="tr,en,de"
                  hint="Virgul ile ayirin. Ilk dil ana dil olarak kabul edilir."
                />
                <Field
                  label="Hedef Keywordler"
                  value={form.keywords}
                  onChange={(value) => setValue('keywords', value)}
                  placeholder="spor ayakkabi, kosu ayakkabisi"
                  hint="Rewrite ve SEO analizinde kullanilir."
                />
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                <ToggleField
                  title="Dry Run"
                  description="Aciksa onaylanan oneriler ikas'a yazilmaz."
                  checked={form.dry_run}
                  onChange={(checked) => setValue('dry_run', checked)}
                />
                <ToggleField
                  title="Thinking Mode"
                  description="Destekleyen providerlarda daha detayli reasoning ister."
                  checked={form.ai_thinking_mode}
                  onChange={(checked) => setValue('ai_thinking_mode', checked)}
                />
              </div>
            </SectionCard>

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
                    onChange={handleProviderChange}
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
                    onClick={handleModelDiscovery}
                    disabled={discoverModelsMut.isPending}
                    className="inline-flex h-11 items-center justify-center rounded-2xl border border-sky-500/40 bg-sky-500/10 px-4 text-sm font-medium text-sky-200 transition hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {discoverModelsMut.isPending ? 'Taraniyor...' : 'Modelleri Tara'}
                  </button>
                </div>
              )}

              {providersQ.error && (
                <p className="mt-4 text-sm text-amber-300">
                  Provider listesi API'den alinamadi. Mevcut secim korunuyor.
                </p>
              )}
            </SectionCard>

            <SectionCard
              eyebrow="Prompt"
              title="Prompt Editoru"
              description="Aciklama ve ceviri promptlarini dosya bazli olarak yonetin."
              actions={
                <button
                  onClick={handleResetAllPrompts}
                  disabled={resetPromptMut.isPending || availablePromptGroups.length === 0}
                  className="rounded-xl border border-slate-700 px-3 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Tumunu Varsayilana Don
                </button>
              }
            >
              {availablePromptGroups.length === 0 ? (
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-400">
                  Prompt metadata yuklenemedi.
                </div>
              ) : (
                <>
                  <div className="mb-5 flex flex-wrap gap-2">
                    {availablePromptGroups.map((group) => (
                      <button
                        key={group.label}
                        onClick={() => setActivePromptGroup(group.label)}
                        className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                          selectedPromptGroup?.label === group.label
                            ? 'bg-sky-500 text-slate-950'
                            : 'border border-slate-700 bg-slate-900/80 text-slate-300 hover:border-slate-500 hover:text-white'
                        }`}
                      >
                        {group.label}
                      </button>
                    ))}
                  </div>

                  <div className="space-y-4">
                    {selectedPromptGroup?.prompts.map((prompt) => (
                      <PromptCard
                        key={prompt.key}
                        template={prompt}
                        value={promptValues[prompt.key] ?? prompt.content}
                        onChange={(value) => handlePromptChange(prompt.key, value)}
                        onReset={() => handlePromptReset(prompt.key)}
                        disabled={resetPromptMut.isPending}
                      />
                    ))}
                  </div>
                </>
              )}
            </SectionCard>
          </div>

          <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
            <SectionCard
              eyebrow="Kontrol"
              title="Kaydet ve Test Et"
              description="Tum degisiklikler bu panelden yonetilir."
            >
              <div className="space-y-3">
                <button
                  onClick={handleSaveAll}
                  disabled={saveAllMut.isPending}
                  className="inline-flex h-12 w-full items-center justify-center rounded-2xl bg-sky-500 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {saveAllMut.isPending ? 'Kaydediliyor...' : 'Tumunu Kaydet'}
                </button>
                <button
                  onClick={handleConnectionTest}
                  disabled={testMut.isPending}
                  className="inline-flex h-12 w-full items-center justify-center rounded-2xl border border-slate-700 bg-slate-900/70 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {testMut.isPending ? 'Test Ediliyor...' : 'Baglanti Testi'}
                </button>
                <button
                  onClick={() => {
                    setBanner(null);
                    mcpInitMut.mutate();
                  }}
                  disabled={mcpInitMut.isPending || !form.mcp_token.trim()}
                  className="inline-flex h-12 w-full items-center justify-center rounded-2xl border border-fuchsia-500/35 bg-fuchsia-500/10 text-sm font-medium text-fuchsia-100 transition hover:bg-fuchsia-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {mcpInitMut.isPending ? 'Baglaniyor...' : 'MCP Baglan'}
                </button>
              </div>

              {banner && <Banner tone={banner.tone} message={banner.message} className="mt-4" />}

              {testMut.data && (
                <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
                  <div className="font-medium text-white">Son baglanti testi</div>
                  <p className="mt-2 leading-6">{testMut.data.message}</p>
                </div>
              )}
            </SectionCard>

            {currentProvider === 'lm-studio' && (
              <SectionCard
                eyebrow="LM Studio"
                title="Anlik Durum"
                description="Secili modelin loaded context bilgisini ve varsa indirme job durumunu gosterir."
              >
                <div className="space-y-4">
                  <label className="block">
                    <span className="mb-1.5 block text-sm font-medium text-slate-200">Download Job ID</span>
                    <input
                      value={downloadJobId}
                      onChange={(event) => setDownloadJobId(event.target.value)}
                      placeholder="Opsiyonel job id"
                      className="h-11 w-full rounded-2xl border border-slate-700 bg-slate-950/90 px-4 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-sky-400"
                    />
                    <span className="mt-2 block text-xs leading-5 text-slate-500">
                      Girersen `/api/v1/models/download/status/:job_id` ile anlik indirme bilgisi izlenir.
                    </span>
                  </label>

                  {lmStudioLiveQ.isError ? (
                    <Banner
                      tone="error"
                      message={formatError(lmStudioLiveQ.error, 'LM Studio anlik durum bilgisi okunamadi.')}
                    />
                  ) : (
                    <>
                      <dl className="space-y-4 text-sm">
                        <StatusRow
                          label="Secili model"
                          value={lmStudioLiveQ.data?.selected_model?.display_name || form.ai_model_name || 'Bilinmiyor'}
                          mono={false}
                        />
                        <StatusRow
                          label="Model durumu"
                          value={lmStudioLiveQ.data?.selected_model?.status || 'Bilinmiyor'}
                          mono={false}
                        />
                        <StatusRow
                          label="Loaded context"
                          value={
                            typeof lmStudioLiveQ.data?.selected_model?.context_length === 'number'
                              ? String(lmStudioLiveQ.data.selected_model.context_length)
                              : 'Bilinmiyor'
                          }
                        />
                      </dl>

                      {lmStudioLiveQ.data?.download_status && (
                        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                          <div className="text-sm font-medium text-white">Download Job</div>
                          <dl className="mt-3 space-y-3 text-sm">
                            <StatusRow
                              label="Durum"
                              value={lmStudioLiveQ.data.download_status.status || 'Bilinmiyor'}
                              mono={false}
                            />
                            <StatusRow
                              label="Indirilen"
                              value={formatByteProgress(
                                lmStudioLiveQ.data.download_status.downloaded_bytes,
                                lmStudioLiveQ.data.download_status.total_size_bytes,
                              )}
                              mono={false}
                            />
                            <StatusRow
                              label="Hiz"
                              value={
                                typeof lmStudioLiveQ.data.download_status.bytes_per_second === 'number'
                                  ? `${formatBytes(lmStudioLiveQ.data.download_status.bytes_per_second)}/sn`
                                  : 'Bilinmiyor'
                              }
                              mono={false}
                            />
                            <StatusRow
                              label="ETA"
                              value={formatIsoDateTime(lmStudioLiveQ.data.download_status.estimated_completion)}
                              mono={false}
                            />
                          </dl>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </SectionCard>
            )}

            <SectionCard
              eyebrow="Durum"
              title="Canli Ozet"
              description="Kayitli konfigirasyonun aktif durumu."
            >
              <dl className="space-y-4 text-sm">
                <StatusRow label="Secili provider" value={currentProvider} />
                <StatusRow label="Model" value={form.ai_model_name || 'Secilmedi'} />
                <StatusRow label="Magaza" value={form.store_name || 'Tanimlanmadi'} />
                <StatusRow label="Diller" value={form.languages || 'tr'} />
                <StatusRow
                  label="Keywords"
                  value={form.keywords || 'Tanimsiz'}
                  mono={false}
                />
                <StatusRow
                  label="Promptlar"
                  value={`${promptCount} duzenlenebilir dosya`}
                />
              </dl>
            </SectionCard>
          </aside>
        </div>
      </div>
    </div>
  );

  function syncPromptGroups(groups: PromptGroup[]) {
    setPromptGroups(groups);
    setPromptValues(flattenPromptValues(groups));
    setActivePromptGroup((prev) => {
      if (prev && groups.some((group) => group.label === prev)) {
        return prev;
      }
      return groups[0]?.label ?? '';
    });
  }
}


function formatBytes(value: number) {
  if (value >= 1024 ** 3) {
    return `${(value / 1024 ** 3).toFixed(2)} GB`;
  }
  if (value >= 1024 ** 2) {
    return `${(value / 1024 ** 2).toFixed(2)} MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${value} B`;
}

function formatByteProgress(downloaded?: number | null, total?: number | null) {
  if (typeof downloaded !== 'number' || typeof total !== 'number' || total <= 0) {
    return 'Bilinmiyor';
  }
  const percent = ((downloaded / total) * 100).toFixed(1);
  return `${formatBytes(downloaded)} / ${formatBytes(total)} (${percent}%)`;
}

function formatIsoDateTime(value?: string) {
  if (!value) {
    return 'Bilinmiyor';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('tr-TR');
}

function toneFromHealth(status?: string): BannerTone {
  if (status === 'ok') {
    return 'success';
  }
  if (status === 'error' || status === 'offline' || status === 'missing_url') {
    return 'error';
  }
  return 'info';
}

function buildModelOptions(provider: string, currentModel: string, discovered: string[]) {
  return uniqueStrings([currentModel, ...discovered, ...(PRESET_MODELS[provider] ?? [])]);
}

function uniqueStrings(values: string[]) {
  const seen = new Set<string>();
  const items: string[] = [];
  for (const value of values) {
    const normalized = value.trim();
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    items.push(normalized);
  }
  return items;
}

function flattenPromptValues(groups: PromptGroup[]) {
  const values: Record<string, string> = {};
  for (const group of groups) {
    for (const prompt of group.prompts) {
      values[prompt.key] = prompt.content;
    }
  }
  return values;
}

function formatError(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}

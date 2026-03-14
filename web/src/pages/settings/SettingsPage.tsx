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
} from '../../api/client';
import type { PromptGroup, SettingsData } from '../../types';
import { StatusPill, type BannerTone } from '../../components/settings/UiPrimitives';
import {
  PROVIDER_META,
  DISCOVERABLE_PROVIDERS,
  buildModelOptions,
  toneFromHealth,
  flattenPromptValues,
  formatError,
} from './constants';
import StoreSettingsSection from './StoreSettingsSection';
import ProviderSection from './ProviderSection';
import PromptEditorSection from './PromptEditorSection';
import ControlSidebar from './ControlSidebar';
import LmStudioStatusCard from './LmStudioStatusCard';
import LiveStatusCard from './LiveStatusCard';

type BannerState = { tone: BannerTone; message: string } | null;

export default function SettingsPage() {
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
    if (settingsQ.data) setForm((prev) => prev ?? settingsQ.data);
  }, [settingsQ.data]);

  useEffect(() => {
    if (!promptsQ.data || promptGroups.length > 0) return;
    syncPromptGroups(promptsQ.data.groups);
  }, [promptGroups.length, promptsQ.data]);

  useEffect(() => {
    if (!form) return;
    const provider = form.ai_provider || 'none';
    const meta = PROVIDER_META[provider] ?? PROVIDER_META.none;
    const fallbackModel = buildModelOptions(provider, '', discoveredModels[provider] ?? [])[0] ?? '';
    setForm((prev) => {
      if (!prev || prev.ai_provider !== provider) return prev;
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

  // ── Mutations ─────────────────────────────────────────────────────────────

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
    onError: (error) => setBanner({ tone: 'error', message: formatError(error, 'Kaydetme sirasinda hata olustu.') }),
  });

  const resetPromptMut = useMutation({
    mutationFn: (promptKeys: string[]) => resetPromptTemplates(promptKeys),
    onSuccess: (data, promptKeys) => {
      syncPromptGroups(data.groups);
      qc.invalidateQueries({ queryKey: ['prompt-templates'] });
      setBanner({
        tone: 'success',
        message: promptKeys.length === 1 ? 'Prompt varsayilan haline donduruldu.' : 'Tum promptlar varsayilan haline donduruldu.',
      });
    },
    onError: (error) => setBanner({ tone: 'error', message: formatError(error, 'Prompt sifirlama basarisiz oldu.') }),
  });

  const testMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => testConnection(values),
    onError: (error) => setBanner({ tone: 'error', message: formatError(error, 'Baglanti testi calismadi.') }),
  });

  const mcpInitMut = useMutation({
    mutationFn: () => initializeMcp(),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['mcp-status'] });
      setBanner({ tone: result.initialized ? 'success' : 'error', message: result.message || 'MCP durumu guncellendi.' });
    },
    onError: (error) => setBanner({ tone: 'error', message: formatError(error, 'MCP baglantisi kurulamadi.') }),
  });

  const discoverModelsMut = useMutation({
    mutationFn: async ({ provider, baseUrl }: { provider: string; baseUrl: string }) => {
      const result = await getProviderModels(provider, baseUrl);
      return { provider, models: result.models };
    },
    onSuccess: ({ provider, models }) => {
      setDiscoveredModels((prev) => ({ ...prev, [provider]: models }));
      setForm((prev) => {
        if (!prev || prev.ai_provider !== provider) return prev;
        if (prev.ai_model_name && models.includes(prev.ai_model_name)) return prev;
        if (!models[0]) return prev;
        return { ...prev, ai_model_name: models[0] };
      });
      setBanner({ tone: models.length > 0 ? 'success' : 'info', message: models.length > 0 ? `${models.length} model bulundu.` : 'Baglanti kuruldu ama model listesi bos dondu.' });
    },
    onError: (error) => setBanner({ tone: 'error', message: formatError(error, 'Model listesi alinamadi.') }),
  });

  // ── Loading / Error ───────────────────────────────────────────────────────

  if ((settingsQ.isLoading && !form) || (promptsQ.isLoading && promptGroups.length === 0)) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-300">Ayar arayuzu yukleniyor...</div>;
  }
  if (!form) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-center text-slate-300">{formatError(settingsQ.error, 'Ayarlar okunamadi.')}</div>;
  }

  // ── Derived ───────────────────────────────────────────────────────────────

  const currentProvider = form.ai_provider || 'none';
  const providerMeta = PROVIDER_META[currentProvider] ?? PROVIDER_META.none;
  const providerOptions = providersQ.data?.providers?.length ? providersQ.data.providers : [{ key: currentProvider, label: currentProvider }];
  const availablePromptGroups = promptGroups.length > 0 ? promptGroups : promptsQ.data?.groups ?? [];
  const selectedPromptGroup = availablePromptGroups.find((g) => g.label === activePromptGroup) ?? availablePromptGroups[0];
  const modelOptions = buildModelOptions(currentProvider, form.ai_model_name, discoveredModels[currentProvider] ?? []);
  const showApiKey = !['none', 'ollama', 'lm-studio'].includes(currentProvider);
  const showBaseUrl = ['openai', 'openrouter', 'ollama', 'lm-studio', 'custom'].includes(currentProvider);
  const useModelSelect = currentProvider !== 'custom' && modelOptions.length > 0;
  const canDiscoverModels = DISCOVERABLE_PROVIDERS.has(currentProvider);
  const promptCount = availablePromptGroups.reduce((t, g) => t + g.prompts.length, 0);

  const setValue = <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

  const handleProviderChange = (nextProvider: string) => {
    const meta = PROVIDER_META[nextProvider] ?? PROVIDER_META.none;
    setForm((prev) => {
      if (!prev) return prev;
      const nextModel = prev.ai_model_name || buildModelOptions(nextProvider, '', discoveredModels[nextProvider] ?? [])[0] || '';
      let nextBaseUrl = prev.ai_base_url;
      if (meta.lockedBaseUrl) nextBaseUrl = meta.lockedBaseUrl;
      else if (!nextBaseUrl && meta.defaultBaseUrl) nextBaseUrl = meta.defaultBaseUrl;
      return { ...prev, ai_provider: nextProvider, ai_base_url: nextBaseUrl, ai_model_name: nextModel };
    });
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(37,99,235,0.25),_transparent_32%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.18),_transparent_24%),linear-gradient(180deg,_#020617,_#0f172a_42%,_#020617)] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-6 flex flex-col gap-4 rounded-3xl border border-slate-800/80 bg-slate-950/65 p-6 shadow-2xl shadow-slate-950/40 backdrop-blur md:flex-row md:items-end md:justify-between">
          <div className="space-y-3">
            <Link to="/" className="inline-flex text-sm text-sky-300 transition hover:text-sky-200">&larr; Dashboard</Link>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-white">Ayar Merkezi</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                AI provider, ikas baglantisi, SEO ayarlari ve prompt dosyalari tek ekrandan yonetilir. Prompt degisiklikleri bir sonraki AI isteginde aktif olur.
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatusPill label="Provider" value={healthQ.data?.message || currentProvider} tone={toneFromHealth(healthQ.data?.status)} />
            <StatusPill label="MCP" value={mcpQ.data?.message || 'Durum okunuyor'} tone={mcpQ.data?.initialized ? 'success' : 'info'} />
            <StatusPill label="Prompt" value={`${promptCount} dosya aktif`} tone="info" />
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <StoreSettingsSection form={form} setValue={setValue} />
            <ProviderSection
              form={form}
              setValue={setValue}
              currentProvider={currentProvider}
              providerMeta={providerMeta}
              providerOptions={providerOptions}
              modelOptions={modelOptions}
              showApiKey={showApiKey}
              showBaseUrl={showBaseUrl}
              useModelSelect={useModelSelect}
              canDiscoverModels={canDiscoverModels}
              onProviderChange={handleProviderChange}
              onModelDiscovery={() => { setBanner(null); discoverModelsMut.mutate({ provider: currentProvider, baseUrl: form.ai_base_url }); }}
              isDiscovering={discoverModelsMut.isPending}
              providerError={providersQ.error as Error | null}
            />
            <PromptEditorSection
              promptGroups={availablePromptGroups}
              selectedGroup={selectedPromptGroup}

              promptValues={promptValues}
              onGroupChange={setActivePromptGroup}
              onPromptChange={(key, value) => setPromptValues((prev) => ({ ...prev, [key]: value }))}
              onPromptReset={(key) => { setBanner(null); resetPromptMut.mutate([key]); }}
              onResetAll={() => { setBanner(null); resetPromptMut.mutate([]); }}
              isResetting={resetPromptMut.isPending}
            />
          </div>

          <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
            <ControlSidebar
              onSave={() => { setBanner(null); saveAllMut.mutate({ settings: form, prompts: promptValues }); }}
              onTest={() => { setBanner(null); testMut.mutate(form as unknown as Record<string, unknown>); }}
              onMcpInit={() => { setBanner(null); mcpInitMut.mutate(); }}
              isSaving={saveAllMut.isPending}
              isTesting={testMut.isPending}
              isMcpConnecting={mcpInitMut.isPending}
              mcpDisabled={!form.mcp_token.trim()}
              banner={banner}
              testResult={testMut.data}
            />
            {currentProvider === 'lm-studio' && (
              <LmStudioStatusCard
                liveStatus={lmStudioLiveQ.data}
                liveStatusError={lmStudioLiveQ.error as Error | null}
                fallbackModelName={form.ai_model_name}
                downloadJobId={downloadJobId}
                onDownloadJobIdChange={setDownloadJobId}
              />
            )}
            <LiveStatusCard
              provider={currentProvider}
              model={form.ai_model_name}
              storeName={form.store_name}
              languages={form.languages}
              keywords={form.keywords}
              promptCount={promptCount}
            />
          </aside>
        </div>
      </div>
    </div>
  );

  function syncPromptGroups(groups: PromptGroup[]) {
    setPromptGroups(groups);
    setPromptValues(flattenPromptValues(groups));
    setActivePromptGroup((prev) => {
      if (prev && groups.some((g) => g.label === prev)) return prev;
      return groups[0]?.label ?? '';
    });
  }
}

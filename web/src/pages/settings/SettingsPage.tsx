import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../../shared/ui/Toast';
import {
  getMcpStatus,
  getLmStudioLiveStatus,
  getProviderHealth,
  getProviderModels,
  getProviders,
  getSettings,
  initializeMcp,
  resetLocalProductData,
  testConnection,
  updateSettings,
} from '../../api/client';
import type { SettingsData } from '../../types';
import type { BannerTone } from '../../components/settings/UiPrimitives';
import {
  PROVIDER_META,
  DISCOVERABLE_PROVIDERS,
  buildModelOptions,
  toneFromHealth,
  formatError,
} from './constants';
import StoreSettingsSection from './StoreSettingsSection';
import ProviderSection from './ProviderSection';
import ControlSidebar from './ControlSidebar';
import LmStudioStatusCard from './LmStudioStatusCard';
import LiveStatusCard from './LiveStatusCard';
import ConfirmDialog from '../../shared/ui/ConfirmDialog';

type BannerState = { tone: BannerTone; message: string } | null;

export default function SettingsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState<SettingsData | null>(null);
  const [discoveredModels, setDiscoveredModels] = useState<Record<string, string[]>>({});
  const [banner, setBanner] = useState<BannerState>(null);
  const [downloadJobId, setDownloadJobId] = useState('');
  const [confirmResetOpen, setConfirmResetOpen] = useState(false);

  const settingsQ = useQuery({ queryKey: ['settings'], queryFn: getSettings });
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
    mutationFn: (settings: SettingsData) => updateSettings(settings as unknown as Record<string, unknown>),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] });
      qc.invalidateQueries({ queryKey: ['provider-health'] });
      qc.invalidateQueries({ queryKey: ['mcp-status'] });
      setBanner({ tone: 'success', message: 'Ayarlar kaydedildi.' });
      toast.success('Ayarlar kaydedildi.');
    },
    onError: (error) => {
      const msg = formatError(error, 'Kaydetme sirasinda hata olustu.');
      setBanner({ tone: 'error', message: msg });
      toast.error(msg);
    },
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

  const resetDbMut = useMutation({
    mutationFn: resetLocalProductData,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['products'] });
      qc.invalidateQueries({ queryKey: ['product'] });
      qc.invalidateQueries({ queryKey: ['suggestions'] });
      setBanner({
        tone: 'success',
        message: `${data.products_deleted} ürün, ${data.scores_deleted} skor ve ${data.suggestions_deleted} öneri silindi.`,
      });
      toast.success('Veritabanı sıfırlandı.');
    },
    onError: (error) => {
      const msg = formatError(error, 'Veritabanı sıfırlama başarısız oldu.');
      setBanner({ tone: 'error', message: msg });
      toast.error(msg);
    },
  });

  // ── Loading / Error ───────────────────────────────────────────────────────

  if (settingsQ.isLoading && !form) {
    return (
      <div className="page-bg flex min-h-screen items-center justify-center" style={{ color: 'var(--color-text-secondary)' }}>
        Ayar arayuzu yukleniyor...
      </div>
    );
  }
  if (!form) {
    return (
      <div className="page-bg flex min-h-screen items-center justify-center px-6 text-center" style={{ color: 'var(--color-text-secondary)' }}>
        {formatError(settingsQ.error, 'Ayarlar okunamadi.')}
      </div>
    );
  }

  // ── Derived ───────────────────────────────────────────────────────────────

  const currentProvider = form.ai_provider || 'none';
  const providerMeta = PROVIDER_META[currentProvider] ?? PROVIDER_META.none;
  const providerOptions = providersQ.data?.providers?.length ? providersQ.data.providers : [{ key: currentProvider, label: currentProvider }];
  const modelOptions = buildModelOptions(currentProvider, form.ai_model_name, discoveredModels[currentProvider] ?? []);
  const showApiKey = !['none', 'ollama', 'lm-studio'].includes(currentProvider);
  const showBaseUrl = ['openai', 'openrouter', 'ollama', 'lm-studio', 'custom'].includes(currentProvider);
  const useModelSelect = currentProvider !== 'custom' && modelOptions.length > 0;
  const canDiscoverModels = DISCOVERABLE_PROVIDERS.has(currentProvider);

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
    <div className="page-bg" style={{ color: 'var(--color-text-primary)' }}>
      <ConfirmDialog
        open={confirmResetOpen}
        title="Veritabanını Sıfırla"
        message="Tüm ürün önbelleği, SEO skorları ve öneriler silinecek. Bu işlem geri alınamaz."
        confirmLabel="Sıfırla"
        cancelLabel="İptal"
        variant="danger"
        onConfirm={() => { setConfirmResetOpen(false); resetDbMut.mutate(); }}
        onCancel={() => setConfirmResetOpen(false)}
      />
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="enterprise-surface mb-6 flex flex-col gap-4 rounded-2xl p-6 md:flex-row md:items-end md:justify-between">
          <div className="space-y-3">
            <Link
              to="/"
              className="inline-flex text-[13px] transition"
              style={{ color: 'var(--color-accent-light)' }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--color-accent)'; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--color-accent-light)'; }}
            >
              &larr; Dashboard
            </Link>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight" style={{ color: 'var(--color-text-primary)' }}>
                Ayar Merkezi
              </h1>
              <p className="mt-2 max-w-2xl text-[13px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
                AI provider, ikas baglantisi ve SEO ayarlarini tek ekrandan yonetin.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="rounded-xl p-3" style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(148,163,184,0.16)' }}>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>Provider</div>
              <div className="mt-1 text-[13px] font-medium" style={{ color: toneFromHealth(healthQ.data?.status) === 'success' ? 'var(--color-success)' : toneFromHealth(healthQ.data?.status) === 'error' ? 'var(--color-danger)' : 'var(--color-text-secondary)' }}>
                {healthQ.data?.message || currentProvider}
              </div>
            </div>
            <div className="rounded-xl p-3" style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(148,163,184,0.16)' }}>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>MCP</div>
              <div className="mt-1 text-[13px] font-medium" style={{ color: mcpQ.data?.initialized ? 'var(--color-success)' : 'var(--color-text-secondary)' }}>
                {mcpQ.data?.message || 'Durum okunuyor'}
              </div>
            </div>
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
          </div>

          <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
            <ControlSidebar
              onSave={() => { setBanner(null); saveAllMut.mutate(form); }}
              onTest={() => { setBanner(null); testMut.mutate(form as unknown as Record<string, unknown>); }}
              onMcpInit={() => { setBanner(null); mcpInitMut.mutate(); }}
              onResetDb={() => setConfirmResetOpen(true)}
              isSaving={saveAllMut.isPending}
              isTesting={testMut.isPending}
              isMcpConnecting={mcpInitMut.isPending}
              isResettingDb={resetDbMut.isPending}
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
            />
          </aside>
        </div>
      </div>
    </div>
  );

}

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSettings,
  updateSettings,
  getProviders,
  getProviderHealth,
  testConnection,
} from '../api/client';
import type { SettingsData } from '../types';

export default function Settings() {
  const qc = useQueryClient();
  const [form, setForm] = useState<SettingsData | null>(null);

  const settingsQ = useQuery({ queryKey: ['settings'], queryFn: getSettings });
  const providersQ = useQuery({ queryKey: ['providers'], queryFn: getProviders });
  const healthQ = useQuery({ queryKey: ['provider-health'], queryFn: getProviderHealth });

  useEffect(() => {
    if (settingsQ.data && !form) setForm(settingsQ.data);
  }, [settingsQ.data, form]);

  const saveMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => updateSettings(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] });
      qc.invalidateQueries({ queryKey: ['provider-health'] });
      alert('Ayarlar kaydedildi.');
    },
  });

  const testMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => testConnection(values),
  });

  if (!form) {
    return <div className="flex h-screen items-center justify-center text-gray-500">Yukleniyor...</div>;
  }

  const set = <K extends keyof SettingsData>(key: K, value: SettingsData[K]) =>
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

  const handleSave = () => saveMut.mutate(form as unknown as Record<string, unknown>);
  const handleTest = () => testMut.mutate(form as unknown as Record<string, unknown>);

  return (
    <div className="mx-auto max-w-3xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Ayarlar</h1>
        <a href="/" className="text-sm text-blue-400 hover:underline">
          &larr; Dashboard
        </a>
      </div>

      <div className="space-y-6">
        {/* ikas */}
        <section className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-400">
            ikas Baglantisi
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Magaza Adi" value={form.store_name} onChange={(v) => set('store_name', v)} />
            <Field label="Client ID" value={form.client_id} onChange={(v) => set('client_id', v)} />
            <Field
              label="Client Secret"
              value={form.client_secret}
              onChange={(v) => set('client_secret', v)}
              type="password"
            />
          </div>
        </section>

        {/* AI Provider */}
        <section className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-400">
            AI Provider
            {healthQ.data && (
              <span className="ml-3 text-xs font-normal text-gray-500">
                {healthQ.data.message}
              </span>
            )}
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs text-gray-500">Provider</label>
              <select
                value={form.ai_provider}
                onChange={(e) => set('ai_provider', e.target.value)}
                className="w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500"
              >
                {providersQ.data?.providers.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <Field label="API Key" value={form.ai_api_key} onChange={(v) => set('ai_api_key', v)} type="password" />
            <Field label="Base URL" value={form.ai_base_url} onChange={(v) => set('ai_base_url', v)} />
            <Field label="Model" value={form.ai_model_name} onChange={(v) => set('ai_model_name', v)} />
            <Field
              label="Temperature"
              value={String(form.ai_temperature)}
              onChange={(v) => set('ai_temperature', parseFloat(v) || 0.7)}
            />
            <Field
              label="Max Tokens"
              value={String(form.ai_max_tokens)}
              onChange={(v) => set('ai_max_tokens', parseInt(v) || 2000)}
            />
          </div>
          <div className="mt-3 flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                checked={form.ai_thinking_mode}
                onChange={(e) => set('ai_thinking_mode', e.target.checked)}
                className="rounded"
              />
              Thinking Mode
            </label>
          </div>
        </section>

        {/* General */}
        <section className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-400">Genel</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Diller (virgul)" value={form.languages} onChange={(v) => set('languages', v)} />
            <Field label="Hedef Keywordler (virgul)" value={form.keywords} onChange={(v) => set('keywords', v)} />
          </div>
          <div className="mt-3">
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                checked={form.dry_run}
                onChange={(e) => set('dry_run', e.target.checked)}
                className="rounded"
              />
              Dry Run (ikas'a yazma)
            </label>
          </div>
        </section>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saveMut.isPending}
            className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {saveMut.isPending ? 'Kaydediliyor...' : 'Kaydet'}
          </button>
          <button
            onClick={handleTest}
            disabled={testMut.isPending}
            className="rounded-lg border border-gray-600 px-6 py-2.5 text-sm font-medium text-gray-300 transition hover:border-gray-500 hover:text-white disabled:opacity-50"
          >
            {testMut.isPending ? 'Test ediliyor...' : 'Baglanti Testi'}
          </button>
          {testMut.data && (
            <span
              className={`self-center text-sm ${testMut.data.ok ? 'text-green-400' : 'text-red-400'}`}
            >
              {testMut.data.message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-gray-500">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500"
      />
    </div>
  );
}

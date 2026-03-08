import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSettings,
  updateSettings,
  getProviders,
  getProviderHealth,
  testConnection,
  getMcpStatus,
  initializeMcp,
} from '../api/client';
import type { SettingsData } from '../types';

export default function Settings() {
  const qc = useQueryClient();
  const [form, setForm] = useState<SettingsData | null>(null);

  const settingsQ = useQuery({ queryKey: ['settings'], queryFn: getSettings });
  const providersQ = useQuery({ queryKey: ['providers'], queryFn: getProviders });
  const healthQ = useQuery({ queryKey: ['provider-health'], queryFn: getProviderHealth });
  const mcpQ = useQuery({ queryKey: ['mcp-status'], queryFn: getMcpStatus });

  useEffect(() => {
    if (settingsQ.data && !form) setForm(settingsQ.data);
  }, [settingsQ.data, form]);

  const saveMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => updateSettings(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] });
      qc.invalidateQueries({ queryKey: ['provider-health'] });
      qc.invalidateQueries({ queryKey: ['mcp-status'] });
      alert('Ayarlar kaydedildi.');
    },
  });

  const testMut = useMutation({
    mutationFn: (values: Record<string, unknown>) => testConnection(values),
  });

  const mcpInitMut = useMutation({
    mutationFn: () => initializeMcp(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcp-status'] }),
  });

  if (!form) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ color: 'var(--color-text-muted)' }}>
        <div className="flex items-center gap-2">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
          Yukleniyor...
        </div>
      </div>
    );
  }

  const set = <K extends keyof SettingsData>(key: K, value: SettingsData[K]) =>
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

  const handleSave = () => saveMut.mutate(form as unknown as Record<string, unknown>);
  const handleTest = () => testMut.mutate(form as unknown as Record<string, unknown>);

  return (
    <div style={{ background: 'var(--color-bg-base)' }} className="min-h-screen">
      {/* Header */}
      <header
        className="flex items-center justify-between px-5 py-3"
        style={{
          background: 'var(--color-bg-surface)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center gap-4">
          <a href="/" className="flex items-center gap-2.5 transition-all hover:opacity-80">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
            >
              iS
            </div>
            <span className="text-[15px] font-semibold text-white tracking-tight">
              ikas <span style={{ color: 'var(--color-primary-light)' }}>SEO Agent</span>
            </span>
          </a>

          <div className="h-5 w-px" style={{ background: 'var(--color-border-light)' }} />

          <span className="text-[13px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Ayarlar
          </span>
        </div>

        <a
          href="/"
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all"
          style={{
            color: 'var(--color-text-secondary)',
            border: '1px solid var(--color-border-light)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--color-text-primary)';
            e.currentTarget.style.background = 'var(--color-bg-hover)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--color-text-secondary)';
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Dashboard
        </a>
      </header>

      <div className="mx-auto max-w-3xl p-8 space-y-6">
        {/* ikas Connection */}
        <Section title="ikas Baglantisi" icon={
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
          </svg>
        }>
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
        </Section>

        {/* MCP */}
        <Section
          title="ikas MCP Entegrasyonu"
          icon={
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
          badge={
            mcpQ.data && (
              <span
                className="text-xs font-normal"
                style={{ color: mcpQ.data.initialized ? '#34d399' : 'var(--color-text-muted)' }}
              >
                {mcpQ.data.message}
              </span>
            )
          }
        >
          <div className="space-y-3">
            <Field
              label="MCP Token"
              value={form.mcp_token}
              onChange={(v) => set('mcp_token', v)}
              type="password"
            />
            <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
              ikas Admin MCP token'i ile AI chat'te magaza verilerine gercek zamanli erisim
              saglanir. Token, ikas admin panelinden alinabilir.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => mcpInitMut.mutate()}
                disabled={mcpInitMut.isPending || !form.mcp_token}
                className="flex items-center gap-1.5 rounded-lg px-4 py-2 text-[13px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
                style={{ background: 'linear-gradient(135deg, #8b5cf6, #a855f7)' }}
              >
                {mcpInitMut.isPending ? (
                  <>
                    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    Baglaniyor...
                  </>
                ) : (
                  'MCP Baglan'
                )}
              </button>
              {mcpQ.data?.initialized && (
                <span className="flex items-center gap-1.5 text-[13px]" style={{ color: '#34d399' }}>
                  <span className="inline-block h-2 w-2 rounded-full animate-pulse-dot" style={{ background: '#34d399' }} />
                  Bagli
                </span>
              )}
              {mcpInitMut.data && !mcpInitMut.data.initialized && (
                <span className="text-[13px]" style={{ color: 'var(--color-danger)' }}>
                  {mcpInitMut.data.message}
                </span>
              )}
            </div>
          </div>
        </Section>

        {/* AI Provider */}
        <Section
          title="AI Provider"
          icon={
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          }
          badge={
            healthQ.data && (
              <span className="text-xs font-normal" style={{ color: 'var(--color-text-muted)' }}>
                {healthQ.data.message}
              </span>
            )
          }
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                Provider
              </label>
              <select
                value={form.ai_provider}
                onChange={(e) => set('ai_provider', e.target.value)}
                className="w-full rounded-lg px-3 py-2 text-[13px] outline-none transition-all"
                style={{
                  background: 'var(--color-bg-base)',
                  border: '1px solid var(--color-border-light)',
                  color: 'var(--color-text-primary)',
                }}
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
            <label className="flex items-center gap-2 text-[13px] cursor-pointer" style={{ color: 'var(--color-text-secondary)' }}>
              <input
                type="checkbox"
                checked={form.ai_thinking_mode}
                onChange={(e) => set('ai_thinking_mode', e.target.checked)}
                className="h-4 w-4 rounded"
                style={{ accentColor: 'var(--color-primary)' }}
              />
              Thinking Mode
            </label>
          </div>
        </Section>

        {/* General */}
        <Section title="Genel" icon={
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
          </svg>
        }>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Diller (virgul)" value={form.languages} onChange={(v) => set('languages', v)} />
            <Field label="Hedef Keywordler (virgul)" value={form.keywords} onChange={(v) => set('keywords', v)} />
          </div>
          <div className="mt-3">
            <label className="flex items-center gap-2 text-[13px] cursor-pointer" style={{ color: 'var(--color-text-secondary)' }}>
              <input
                type="checkbox"
                checked={form.dry_run}
                onChange={(e) => set('dry_run', e.target.checked)}
                className="h-4 w-4 rounded"
                style={{ accentColor: 'var(--color-primary)' }}
              />
              Dry Run (ikas'a yazma)
            </label>
          </div>
        </Section>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleSave}
            disabled={saveMut.isPending}
            className="flex items-center gap-1.5 rounded-lg px-5 py-2.5 text-[13px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            {saveMut.isPending ? (
              <>
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Kaydediliyor...
              </>
            ) : (
              'Kaydet'
            )}
          </button>
          <button
            onClick={handleTest}
            disabled={testMut.isPending}
            className="rounded-lg px-5 py-2.5 text-[13px] font-medium transition-all"
            style={{
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border-light)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-text-primary)';
              e.currentTarget.style.background = 'var(--color-bg-hover)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-text-secondary)';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            {testMut.isPending ? 'Test ediliyor...' : 'Baglanti Testi'}
          </button>
          {testMut.data && (
            <span
              className="text-[13px] font-medium"
              style={{ color: testMut.data.ok ? '#34d399' : 'var(--color-danger)' }}
            >
              {testMut.data.message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Reusable Components ──────────────────────────────────────────────── */

function Section({
  title,
  icon,
  badge,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      className="rounded-xl p-5"
      style={{
        background: 'var(--glass-bg)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div className="mb-4 flex items-center gap-2">
        {icon && (
          <span style={{ color: 'var(--color-primary-light)' }}>{icon}</span>
        )}
        <h2
          className="text-[13px] font-semibold uppercase tracking-wider"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {title}
        </h2>
        {badge}
      </div>
      {children}
    </section>
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
      <label
        className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg px-3 py-2 text-[13px] outline-none transition-all"
        style={{
          background: 'var(--color-bg-base)',
          border: '1px solid var(--color-border-light)',
          color: 'var(--color-text-primary)',
        }}
        onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
        onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--color-border-light)')}
      />
    </div>
  );
}

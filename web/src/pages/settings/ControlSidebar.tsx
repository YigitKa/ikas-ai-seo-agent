import { Banner, SectionCard } from '../../components/settings/UiPrimitives';
import type { BannerTone } from '../../components/settings/UiPrimitives';

type BannerState = {
  tone: BannerTone;
  message: string;
} | null;

interface ControlSidebarProps {
  onSave: () => void;
  onTest: () => void;
  onMcpInit: () => void;
  isSaving: boolean;
  isTesting: boolean;
  isMcpConnecting: boolean;
  mcpDisabled: boolean;
  banner: BannerState;
  testResult?: { message: string } | null;
}

export default function ControlSidebar({
  onSave,
  onTest,
  onMcpInit,
  isSaving,
  isTesting,
  isMcpConnecting,
  mcpDisabled,
  banner,
  testResult,
}: ControlSidebarProps) {
  return (
    <SectionCard
      eyebrow="Kontrol"
      title="Kaydet ve Test Et"
      description="Tum degisiklikler bu panelden yonetilir."
    >
      <div className="space-y-3">
        <button
          onClick={onSave}
          disabled={isSaving}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-sky-500 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSaving && (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isSaving ? 'Kaydediliyor...' : 'Tumunu Kaydet'}
        </button>
        <button
          onClick={onTest}
          disabled={isTesting}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl border border-slate-700 bg-slate-900/70 text-sm font-medium text-slate-200 transition hover:border-slate-500 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isTesting && (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isTesting ? 'Test Ediliyor...' : 'Baglanti Testi'}
        </button>
        <button
          onClick={onMcpInit}
          disabled={isMcpConnecting || mcpDisabled}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl border border-fuchsia-500/35 bg-fuchsia-500/10 text-sm font-medium text-fuchsia-100 transition hover:bg-fuchsia-500/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isMcpConnecting && (
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          {isMcpConnecting ? 'Baglaniyor...' : 'MCP Baglan'}
        </button>
      </div>

      {banner && <Banner tone={banner.tone} message={banner.message} className="mt-4" />}

      {testResult && (
        <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
          <div className="font-medium text-white">Son baglanti testi</div>
          <p className="mt-2 leading-6">{testResult.message}</p>
        </div>
      )}
    </SectionCard>
  );
}

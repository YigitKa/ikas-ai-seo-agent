import {
  EnterpriseButton,
  EnterpriseBanner,
  EnterpriseSectionCard,
} from '../../shared/ui/EnterprisePrimitives';
import type { BannerTone } from '../../components/settings/UiPrimitives';

type BannerState = {
  tone: BannerTone;
  message: string;
} | null;

interface ControlSidebarProps {
  onSave: () => void;
  onTest: () => void;
  onMcpInit: () => void;
  onResetDb: () => void;
  isSaving: boolean;
  isTesting: boolean;
  isMcpConnecting: boolean;
  isResettingDb: boolean;
  mcpDisabled: boolean;
  banner: BannerState;
  testResult?: { message: string } | null;
}

function SpinIcon() {
  return (
    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

export default function ControlSidebar({
  onSave,
  onTest,
  onMcpInit,
  onResetDb,
  isSaving,
  isTesting,
  isMcpConnecting,
  isResettingDb,
  mcpDisabled,
  banner,
  testResult,
}: ControlSidebarProps) {
  return (
    <EnterpriseSectionCard
      eyebrow="Kontrol"
      title="Kaydet ve Test Et"
      description="Tum degisiklikler bu panelden yonetilir."
    >
      <div className="space-y-3">
        <EnterpriseButton
          onClick={onSave}
          disabled={isSaving}
          tone="primary"
          size="lg"
          fullWidth
        >
          {isSaving && <SpinIcon />}
          {isSaving ? 'Kaydediliyor...' : 'Tumunu Kaydet'}
        </EnterpriseButton>

        <EnterpriseButton
          onClick={onTest}
          disabled={isTesting}
          tone="neutral"
          size="lg"
          fullWidth
        >
          {isTesting && <SpinIcon />}
          {isTesting ? 'Test Ediliyor...' : 'Baglanti Testi'}
        </EnterpriseButton>

        {/* MCP button keeps its own fuchsia theme */}
        <button
          type="button"
          onClick={onMcpInit}
          disabled={isMcpConnecting || mcpDisabled}
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl text-sm font-medium transition-all duration-200 hover:-translate-y-0.5 hover:brightness-110 disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40"
          style={{
            background: 'rgba(168,85,247,0.14)',
            border: '1px solid rgba(168,85,247,0.38)',
            color: '#e9d5ff',
          }}
        >
          {isMcpConnecting && <SpinIcon />}
          {isMcpConnecting ? 'Baglaniyor...' : 'MCP Baglan'}
        </button>
      </div>

      {banner && <EnterpriseBanner tone={banner.tone} message={banner.message} className="mt-4" />}

      {testResult && (
        <div className="enterprise-list-item mt-4 rounded-xl p-4 transition-all duration-200">
          <div className="text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
            Son baglanti testi
          </div>
          <p className="mt-2 text-[13px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
            {testResult.message}
          </p>
        </div>
      )}

      <div className="mt-6 pt-5" style={{ borderTop: '1px solid var(--color-divider)' }}>
        <div
          className="mb-2 text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: 'rgba(239,68,68,0.7)' }}
        >
          Tehlikeli Islemler
        </div>
        <EnterpriseButton
          onClick={onResetDb}
          disabled={isResettingDb}
          tone="danger"
          size="lg"
          fullWidth
        >
          {isResettingDb && <SpinIcon />}
          {isResettingDb ? 'Sifirlaniyor...' : 'DB Sifirla'}
        </EnterpriseButton>
        <p className="mt-1.5 text-center text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          Urun onbellegi, skorlar ve oneriler silinir
        </p>
      </div>
    </EnterpriseSectionCard>
  );
}

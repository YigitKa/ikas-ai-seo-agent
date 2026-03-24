import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

function SpinnerIcon() {
  return (
    <svg
      className="h-3.5 w-3.5 animate-spin"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  );
}

interface ActionButtonProps {
  label: string;
  pendingLabel: string;
  pending: boolean;
  gradient: string;
  onClick: () => void;
  children: ReactNode;
}

function ActionButton({
  label,
  pendingLabel,
  pending,
  gradient,
  onClick,
  children,
}: ActionButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={pending}
      className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
      style={{ background: gradient }}
    >
      {pending ? <SpinnerIcon /> : children}
      {pending ? pendingLabel : label}
    </button>
  );
}

interface DashboardHeaderProps {
  totalCount?: number;
  syncPending: boolean;
  onSync: () => void;
}

export default function DashboardHeader({
  totalCount,
  syncPending,
  onSync,
}: DashboardHeaderProps) {
  return (
    <header
      className="flex items-center justify-between px-5 py-3"
      style={{
        background: 'var(--color-bg-surface)',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            iS
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-white">
            ikas <span style={{ color: 'var(--color-primary-light)' }}>SEO Agent</span>
          </span>
        </div>

        <div className="h-5 w-px" style={{ background: 'var(--color-border-light)' }} />

        <ActionButton
          label="Tum Urunleri Cek"
          pendingLabel="Senkronlaniyor..."
          pending={syncPending}
          gradient="linear-gradient(135deg, #6366f1, #8b5cf6)"
          onClick={onSync}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </ActionButton>


      </div>

      <div className="flex items-center gap-3">
        <Link
          to="/llms"
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white transition-all hover:translate-y-[-1px]"
          style={{
            background: 'linear-gradient(135deg, #06b6d4, #6366f1)',
            boxShadow: '0 10px 30px rgba(99,102,241,0.28)',
          }}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M4 12h10M4 17h7" />
          </svg>
          llms Studio
        </Link>

        <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)', opacity: 0.6 }}>
          build {new Date(__BUILD_TIME__).toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
        </span>

        {typeof totalCount === 'number' && (
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {totalCount} urun
          </span>
        )}

        <Link
          to="/settings"
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors hover:bg-[var(--color-bg-hover)]"
          style={{
            color: 'var(--color-text-secondary)',
            border: '1px solid var(--color-border-light)',
          }}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Ayarlar
        </Link>
      </div>
    </header>
  );
}

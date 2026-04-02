interface DashboardEmptyStateProps {
  requestedSkillSlug?: string;
}

export default function DashboardEmptyState({ requestedSkillSlug }: DashboardEmptyStateProps) {
  return (
    <div className="mb-4">
      <div
        className="rounded-2xl border px-6 py-5 text-center"
        style={{ background: 'var(--glass-bg)', border: '1px solid var(--color-border)' }}
      >
        <div
          className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)' }}
        >
          <svg
            className="h-7 w-7"
            style={{ color: 'var(--color-text-muted)' }}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
            />
          </svg>
        </div>
        <p className="text-[15px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
          Urun secmeden de chat kullanabilirsiniz
        </p>
        <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Soldaki listeden bir urun secerseniz urun baglami ve SEO skoru eklenir. Secmezseniz genel chat modunda devam edersiniz.
        </p>
        {requestedSkillSlug && (
          <p className="mt-3 text-[12px]" style={{ color: 'var(--color-primary-light)' }}>
            Skill Studio'dan gelen `{requestedSkillSlug}` skill'i bu oturum icin uygulanacak.
          </p>
        )}
      </div>
    </div>
  );
}

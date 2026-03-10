export default function DashboardEmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="text-center">
        <div
          className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl"
          style={{ background: 'var(--glass-bg)', border: '1px solid var(--color-border)' }}
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
          Bir urun secin
        </p>
        <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Soldaki listeden bir urun secin. SEO skoru ve chat paneli acilacak.
        </p>
      </div>
    </div>
  );
}

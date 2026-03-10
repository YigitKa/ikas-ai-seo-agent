import ProductTable from '../ProductTable';
import { FILTER_LABELS, FILTER_TABS, type FilterTab } from './constants';
import type { ProductWithScore } from '../../types';

interface DashboardSidebarProps {
  items: ProductWithScore[];
  selectedId: string | null;
  isLoading: boolean;
  filter: FilterTab;
  page: number;
  totalPages: number;
  onSelect: (id: string) => void;
  onFilterChange: (nextFilter: FilterTab) => void;
  onPageChange: (nextPage: number) => void;
}

export default function DashboardSidebar({
  items,
  selectedId,
  isLoading,
  filter,
  page,
  totalPages,
  onSelect,
  onFilterChange,
  onPageChange,
}: DashboardSidebarProps) {
  return (
    <aside
      className="flex w-[340px] flex-col"
      style={{
        background: 'var(--color-bg-surface)',
        borderRight: '1px solid var(--color-border)',
      }}
    >
      <div className="flex gap-1 px-3 py-2.5" style={{ borderBottom: '1px solid var(--color-border)' }}>
        {FILTER_TABS.map((tabKey) => {
          const active = tabKey === filter;
          return (
            <button
              key={tabKey}
              onClick={() => onFilterChange(tabKey)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                active ? '' : 'hover:text-[var(--color-text-secondary)]'
              }`}
              style={{
                background: active ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                color: active ? 'var(--color-primary-light)' : 'var(--color-text-muted)',
              }}
            >
              {FILTER_LABELS[tabKey]}
            </button>
          );
        })}
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="space-y-2 p-3">
            {[...Array(8)].map((_, index) => (
              <div key={index} className="animate-shimmer h-14 rounded-lg" />
            ))}
          </div>
        ) : (
          <ProductTable items={items} selectedId={selectedId} onSelect={onSelect} />
        )}
      </div>

      {totalPages > 1 && (
        <div
          className="flex items-center justify-between px-3 py-2 text-xs"
          style={{
            borderTop: '1px solid var(--color-border)',
            color: 'var(--color-text-muted)',
          }}
        >
          <button
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="rounded px-2 py-1 transition-colors hover:text-white disabled:opacity-30"
          >
            Onceki
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="rounded px-2 py-1 transition-colors hover:text-white disabled:opacity-30"
          >
            Sonraki
          </button>
        </div>
      )}
    </aside>
  );
}

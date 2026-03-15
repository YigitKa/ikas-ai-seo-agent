import { useState, useMemo } from 'react';
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
  const [searchQuery, setSearchQuery] = useState('');

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items;
    const q = searchQuery.toLowerCase();
    return items.filter(
      ({ product }) =>
        product.name.toLowerCase().includes(q) ||
        (product.category && product.category.toLowerCase().includes(q)),
    );
  }, [items, searchQuery]);

  return (
    <aside
      className="flex w-[340px] flex-col"
      style={{
        background: 'var(--color-bg-surface)',
        borderRight: '1px solid var(--color-border)',
      }}
    >
      {/* Search */}
      <div className="px-3 pt-2.5 pb-1.5" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <div className="relative">
          <svg
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2"
            style={{ color: 'var(--color-text-muted)' }}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Urun ara..."
            className="w-full rounded-lg py-1.5 pl-8 pr-3 text-xs outline-none transition-colors placeholder:text-[var(--color-text-muted)]"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: 'var(--color-text-primary)',
            }}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 transition-colors hover:opacity-70"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Filter tabs */}
        <div className="mt-1.5 flex gap-1">
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
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="space-y-2 p-3">
            {[...Array(8)].map((_, index) => (
              <div key={index} className="animate-shimmer h-14 rounded-lg" />
            ))}
          </div>
        ) : (
          <ProductTable items={filteredItems} selectedId={selectedId} onSelect={onSelect} />
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

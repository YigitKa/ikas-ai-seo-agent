import { useState, useMemo } from 'react';
import ProductTable from '../ProductTable';
import { FILTER_LABELS, FILTER_TABS, type FilterTab } from './constants';
import type { ProductWithScore } from '../../types';
import { EnterpriseButton, EnterpriseInput } from '../../shared/ui/EnterprisePrimitives';

interface DashboardSidebarProps {
  items: ProductWithScore[];
  selectedId: string | null;
  isLoading: boolean;
  filter: FilterTab;
  page: number;
  totalPages: number;
  totalCount?: number;
  isSyncing?: boolean;
  onSelect: (id: string) => void;
  onFilterChange: (nextFilter: FilterTab) => void;
  onPageChange: (nextPage: number) => void;
  onSync: () => void;
}

export default function DashboardSidebar({
  items,
  selectedId,
  isLoading,
  filter,
  page,
  totalPages,
  totalCount,
  isSyncing = false,
  onSelect,
  onFilterChange,
  onPageChange,
  onSync,
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
      className="enterprise-panel-divider flex w-[320px] flex-col xl:w-[336px]"
      style={{
        background: 'linear-gradient(180deg, var(--surface-code), var(--surface-panel))',
      }}
    >
      <div className="px-3 py-3" style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div
              className="text-[10px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Urun listesi
            </div>
            <div className="mt-1 text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {typeof totalCount === 'number' ? `${totalCount} urun` : 'Katalog yukleniyor'}
            </div>
          </div>

          <EnterpriseButton
            onClick={onSync}
            disabled={isSyncing}
            tone="primary"
            size="sm"
            className="flex-shrink-0 whitespace-nowrap px-2.5"
          >
            {isSyncing ? 'Sync...' : 'Sync'}
          </EnterpriseButton>
        </div>

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
          <EnterpriseInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Urun ara..."
            className="py-2 pl-8 pr-8"
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

        <div className="mt-2 grid grid-cols-5 gap-1">
          {FILTER_TABS.map((tabKey) => {
            const active = tabKey === filter;
            return (
              <button
                key={tabKey}
                onClick={() => onFilterChange(tabKey)}
                className={`min-w-0 rounded-lg px-2 py-1.5 text-[11px] font-medium leading-tight transition-all duration-200 ${active ? '' : 'hover:text-[var(--color-text-secondary)]'}`}
                style={{
                  background: active ? 'linear-gradient(135deg, rgba(30,64,175,0.42), rgba(67,56,202,0.3))' : 'var(--surface-card)',
                  border: active ? '1px solid rgba(96,165,250,0.36)' : '1px solid var(--color-divider)',
                  color: active ? 'var(--color-text-info)' : 'var(--color-text-muted)',
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
              <div key={index} className="animate-shimmer h-12 rounded-lg" />
            ))}
          </div>
        ) : filteredItems.length === 0 && searchQuery.trim() ? (
          <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
            <svg
              className="h-8 w-8"
              style={{ color: 'var(--color-text-muted)', opacity: 0.5 }}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <div>
              <p className="text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                «{searchQuery}» için sonuç bulunamadı
              </p>
              <p className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                Farklı bir arama deneyin
              </p>
            </div>
            <EnterpriseButton
              onClick={() => setSearchQuery('')}
              tone="primary"
              className="text-[12px]"
            >
              Aramayı Temizle
            </EnterpriseButton>
          </div>
        ) : (
          <ProductTable items={filteredItems} selectedId={selectedId} onSelect={onSelect} />
        )}
      </div>

      {totalPages > 1 && (
        <div
          className="flex items-center justify-between px-3 py-2 text-xs"
          style={{
            borderTop: '1px solid var(--color-border-subtle)',
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

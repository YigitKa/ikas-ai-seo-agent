import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { BatchConfig, ProductWithScore } from '../../types';
import { getSettings } from '../../api/client';
import { fetchProducts, getCategories } from '../../api/client';

const FIELD_OPTIONS: { key: string; label: string }[] = [
  { key: 'meta_title', label: 'Meta Başlık' },
  { key: 'meta_description', label: 'Meta Açıklama' },
  { key: 'name', label: 'Ürün Başlığı' },
  { key: 'description', label: 'Açıklama (TR)' },
  { key: 'description_en', label: 'Açıklama (EN)' },
];

interface Props {
  config: BatchConfig;
  onChange: (config: BatchConfig) => void;
  onStartAnalysis: (productIds: string[]) => void;
  disabled: boolean;
}

function getScoreColor(score: number) {
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#f59e0b';
  return '#ef4444';
}

export default function ProductSelector({ config, onChange, onStartAnalysis, disabled }: Props) {
  const [search, setSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const limit = 50;

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['batchProducts', page],
    queryFn: () => fetchProducts(page, limit, 'all'),
  });

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 60_000,
  });
  const isDryRun = settings?.dry_run ?? true;

  const products: ProductWithScore[] = data?.items ?? [];
  const totalCount = data?.total_count ?? 0;
  const totalPages = Math.ceil(totalCount / limit);

  // Client-side filter
  const filtered = useMemo(() => {
    let list = products;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(p => p.product.name.toLowerCase().includes(q));
    }
    if (config.category_filter) {
      const cat = config.category_filter.toLowerCase();
      list = list.filter(p => (p.product.category || '').toLowerCase().includes(cat));
    }
    if (config.score_threshold < 100) {
      list = list.filter(p => (p.score?.total_score ?? 100) < config.score_threshold);
    }
    return list;
  }, [products, search, config.category_filter, config.score_threshold]);

  const allFilteredIds = new Set(filtered.map(p => p.product.id));
  const allSelected = filtered.length > 0 && filtered.every(p => selectedIds.has(p.product.id));

  function toggleAll() {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (allSelected) {
        allFilteredIds.forEach(id => next.delete(id));
      } else {
        allFilteredIds.forEach(id => next.add(id));
      }
      return next;
    });
  }

  function toggle(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-5">
      {/* ── Filters ── */}
      <div
        className="rounded-xl p-5"
        style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
      >
        <h3
          className="mb-4 text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Filtreler
        </h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {/* Search */}
          <div>
            <label className="mb-1 block text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              Ürün Ara
            </label>
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Ürün adı..."
              className="w-full rounded-lg px-3 py-2 text-[13px]"
              style={{
                background: 'var(--color-bg-primary)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>
          {/* Category */}
          <div>
            <label className="mb-1 block text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              Kategori
            </label>
            <select
              value={config.category_filter}
              onChange={e => onChange({ ...config, category_filter: e.target.value })}
              className="w-full rounded-lg px-3 py-2 text-[13px]"
              style={{
                background: 'var(--color-bg-primary)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            >
              <option value="" style={{ background: '#1e1e2e' }}>Tüm Kategoriler</option>
              {categories.map(c => (
                <option key={c} value={c} style={{ background: '#1e1e2e' }}>{c}</option>
              ))}
            </select>
          </div>
          {/* Score threshold */}
          <div>
            <label className="mb-1 block text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              SEO Eşiği (max skor)
            </label>
            <input
              type="number"
              min={0}
              max={100}
              value={config.score_threshold}
              onChange={e => onChange({ ...config, score_threshold: Number(e.target.value) })}
              className="w-full rounded-lg px-3 py-2 text-[13px]"
              style={{
                background: 'var(--color-bg-primary)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>
        </div>
      </div>

      {/* ── Config ── */}
      <div
        className="rounded-xl p-5"
        style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
      >
        <h3
          className="mb-4 text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Ayarlar
        </h3>

        {/* Target fields */}
        <div className="mb-4">
          <p className="mb-2 text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Güncellenecek Alanlar
          </p>
          <div className="flex flex-wrap gap-2">
            {FIELD_OPTIONS.map(f => {
              const active = config.target_fields.includes(f.key);
              return (
                <button
                  key={f.key}
                  onClick={() => {
                    const fields = active
                      ? config.target_fields.filter(k => k !== f.key)
                      : [...config.target_fields, f.key];
                    onChange({ ...config, target_fields: fields.length ? fields : [f.key] });
                  }}
                  className="rounded-full px-3 py-1.5 text-[12px] font-medium transition"
                  style={{
                    background: active ? 'rgba(99,102,241,0.15)' : 'var(--color-bg-primary)',
                    border: `1px solid ${active ? 'rgba(99,102,241,0.4)' : 'var(--color-border)'}`,
                    color: active ? '#818cf8' : 'var(--color-text-muted)',
                  }}
                >
                  {active && '✓ '}{f.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Constraints row */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
            <input
              type="checkbox"
              checked={config.preserve_specs}
              onChange={e => onChange({ ...config, preserve_specs: e.target.checked })}
              className="rounded"
            />
            Teknik verileri koru (materyal, boyut, ağırlık)
          </label>
          <label className="flex items-center gap-2 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
            <input
              type="checkbox"
              checked={config.prevent_cannibalization}
              onChange={e => onChange({ ...config, prevent_cannibalization: e.target.checked })}
              className="rounded"
            />
            Kanibalizasyon önleme (LSI varyasyonları)
          </label>
        </div>

        {/* Max title change */}
        <div className="mt-3">
          <div className="flex items-center justify-between">
            <span className="text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
              Maks. Başlık Değişimi
            </span>
            <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              %{config.max_title_change_pct}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={config.max_title_change_pct}
            onChange={e => onChange({ ...config, max_title_change_pct: Number(e.target.value) })}
            className="mt-1 w-full"
          />
        </div>
      </div>

      {/* ── Product list ── */}
      <div
        className="rounded-xl"
        style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
      >
        {/* Table header */}
        <div
          className="flex items-center gap-3 px-4 py-3"
          style={{ borderBottom: '1px solid var(--color-border)' }}
        >
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleAll}
            className="rounded"
          />
          <span className="flex-1 text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
            {selectedIds.size > 0
              ? `${selectedIds.size} ürün seçildi`
              : `${filtered.length} ürün listeleniyor`}
          </span>
          {filtered.length > 0 && (
            <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              Sayfa {page}/{totalPages}
            </span>
          )}
        </div>

        {/* Rows */}
        <div className="max-h-[420px] overflow-y-auto">
          {isLoading ? (
            <div className="p-8 text-center text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
              Ürünler yükleniyor...
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-8 text-center text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
              Filtrelere uygun ürün bulunamadı.
            </div>
          ) : (
            filtered.map(item => {
              const p = item.product;
              const score = item.score?.total_score ?? null;
              const selected = selectedIds.has(p.id);
              return (
                <div
                  key={p.id}
                  className="flex cursor-pointer items-center gap-3 px-4 py-2.5 transition hover:opacity-80"
                  style={{
                    borderBottom: '1px solid var(--color-border)',
                    background: selected ? 'rgba(99,102,241,0.06)' : 'transparent',
                  }}
                  onClick={() => toggle(p.id)}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggle(p.id)}
                    className="rounded"
                    onClick={e => e.stopPropagation()}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      {p.name}
                    </p>
                    {p.category && (
                      <p className="truncate text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                        {p.category}
                      </p>
                    )}
                  </div>
                  {score !== null && (
                    <span
                      className="rounded-full px-2 py-0.5 text-[11px] font-bold"
                      style={{
                        background: `${getScoreColor(score)}15`,
                        color: getScoreColor(score),
                      }}
                    >
                      {score}
                    </span>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div
            className="flex items-center justify-center gap-2 px-4 py-3"
            style={{ borderTop: '1px solid var(--color-border)' }}
          >
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
              className="rounded px-3 py-1 text-[12px] disabled:opacity-30"
              style={{ background: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)' }}
            >
              ← Önceki
            </button>
            <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              className="rounded px-3 py-1 text-[12px] disabled:opacity-30"
              style={{ background: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)' }}
            >
              Sonraki →
            </button>
          </div>
        )}
      </div>

      {/* ── DRY_RUN Warning ── */}
      {isDryRun && (
        <div
          className="rounded-lg p-3"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}
        >
          <p className="text-[12px] font-semibold" style={{ color: '#f59e0b' }}>
            ⚠ Güvenli Mod (DRY_RUN) Aktif
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
            Değişiklikler yalnızca taslak olarak kaydedilecek. Canlı uygulamak için Ayarlar → DRY_RUN seçeneğini kapatın.
          </p>
        </div>
      )}

      {/* ── CTA ── */}
      <button
        disabled={disabled || selectedIds.size === 0}
        onClick={() => onStartAnalysis(Array.from(selectedIds))}
        className="w-full rounded-xl py-3.5 text-[14px] font-semibold text-white transition disabled:opacity-40"
        style={{ background: '#6366f1' }}
      >
        {selectedIds.size > 0
          ? `${selectedIds.size} Ürünü Analiz Et`
          : 'Ürün Seçin'}
      </button>
    </div>
  );
}

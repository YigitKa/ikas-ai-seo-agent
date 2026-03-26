import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { BatchConfig, Product, ProductWithScore, SeoScore } from '../../types';
import { fetchProducts, getCategories, getSettings } from '../../api/client';
import { getScoreColor, getStatusBadgeStyle } from '../../shared/score/scoreUtils';

type TargetFieldKey = 'meta_title' | 'meta_description' | 'name' | 'description' | 'description_en';
type ScoreFieldKey = 'title_score' | 'description_score' | 'english_description_score' | 'meta_score' | 'meta_desc_score';
type ScoreThresholdKey =
  | 'title_score_threshold'
  | 'description_score_threshold'
  | 'english_description_score_threshold'
  | 'meta_score_threshold'
  | 'meta_desc_score_threshold';
type SortFieldKey =
  | 'name'
  | 'category'
  | 'sku'
  | 'has_english_description'
  | 'total_score'
  | 'title_score'
  | 'description_score'
  | 'english_description_score'
  | 'meta_score'
  | 'meta_desc_score';
type SortDirection = 'asc' | 'desc';

type FieldScoreThresholds = Record<ScoreThresholdKey, number>;

interface FieldOption {
  key: TargetFieldKey;
  label: string;
  badgeLabel: string;
  scoreKey: ScoreFieldKey;
  thresholdKey: ScoreThresholdKey;
  max: number;
  hint: string;
}

interface SortOption {
  key: SortFieldKey;
  label: string;
}

const FIELD_OPTIONS: FieldOption[] = [
  {
    key: 'meta_title',
    label: 'Meta Başlık',
    badgeLabel: 'Meta Title',
    scoreKey: 'meta_score',
    thresholdKey: 'meta_score_threshold',
    max: 15,
    hint: 'Meta title skoru düşük ürünleri ayrı filtrele.',
  },
  {
    key: 'meta_description',
    label: 'Meta Açıklama',
    badgeLabel: 'Meta Desc',
    scoreKey: 'meta_desc_score',
    thresholdKey: 'meta_desc_score_threshold',
    max: 10,
    hint: 'Meta description kalitesi düşük ürünleri ayrı filtrele.',
  },
  {
    key: 'name',
    label: 'Ürün Başlığı',
    badgeLabel: 'Başlık',
    scoreKey: 'title_score',
    thresholdKey: 'title_score_threshold',
    max: 15,
    hint: 'Başlık skoru düşük ürünleri odak listesine çek.',
  },
  {
    key: 'description',
    label: 'Açıklama (TR)',
    badgeLabel: 'TR Açıklama',
    scoreKey: 'description_score',
    thresholdKey: 'description_score_threshold',
    max: 20,
    hint: 'Türkçe açıklama skoru düşük ürünleri ayrı tara.',
  },
  {
    key: 'description_en',
    label: 'Açıklama (EN)',
    badgeLabel: 'EN Açıklama',
    scoreKey: 'english_description_score',
    thresholdKey: 'english_description_score_threshold',
    max: 5,
    hint: 'İngilizce açıklama kalitesi veya eksiği için ayrı filtre kullan.',
  },
];

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200];
const DEFAULT_FIELD_SCORE_THRESHOLDS: FieldScoreThresholds = {
  title_score_threshold: 100,
  description_score_threshold: 100,
  english_description_score_threshold: 100,
  meta_score_threshold: 100,
  meta_desc_score_threshold: 100,
};
const BASE_SORT_OPTIONS: SortOption[] = [
  { key: 'name', label: 'Ürün Adı' },
  { key: 'category', label: 'Kategori' },
  { key: 'sku', label: 'SKU' },
  { key: 'total_score', label: 'Toplam Skor' },
];
const FIELD_SORT_OPTIONS: Record<TargetFieldKey, SortOption> = {
  meta_title: { key: 'meta_score', label: 'Meta Başlık Skoru' },
  meta_description: { key: 'meta_desc_score', label: 'Meta Açıklama Skoru' },
  name: { key: 'title_score', label: 'Başlık Skoru' },
  description: { key: 'description_score', label: 'TR Açıklama Skoru' },
  description_en: { key: 'english_description_score', label: 'EN Açıklama Skoru' },
};
const SCORE_FIELD_MAX_MAP: Record<ScoreFieldKey, number> = {
  title_score: 15,
  description_score: 20,
  english_description_score: 5,
  meta_score: 15,
  meta_desc_score: 10,
};

interface Props {
  config: BatchConfig;
  onChange: (config: BatchConfig) => void;
  onStartAnalysis: (productIds: string[]) => void;
  disabled: boolean;
}

function normalizeScore(rawValue: number, maxScore: number) {
  if (maxScore <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((Math.max(0, rawValue) / maxScore) * 100)));
}

function stripHtml(value: string) {
  return value
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<\/li>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\r/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}

function hasEnglishDescription(product: Product) {
  return stripHtml(product.description_translations?.en || '').length > 0;
}

function getFieldScore(score: SeoScore | null | undefined, field: FieldOption) {
  if (!score) return null;
  return normalizeScore(score[field.scoreKey], field.max);
}

function normalizeText(value: string | null | undefined) {
  return (value || '').trim().toLocaleLowerCase('tr-TR');
}

function getSortValue(item: ProductWithScore, sortBy: SortFieldKey) {
  const { product, score } = item;
  if (sortBy === 'name') return normalizeText(product.name);
  if (sortBy === 'category') return normalizeText(product.category);
  if (sortBy === 'sku') return normalizeText(product.sku);
  if (sortBy === 'has_english_description') return hasEnglishDescription(product) ? 1 : 0;
  if (sortBy === 'total_score') return score?.total_score ?? -1;

  const max = SCORE_FIELD_MAX_MAP[sortBy as ScoreFieldKey];
  const rawScore = score?.[sortBy as ScoreFieldKey] ?? 0;
  return normalizeScore(rawScore, max);
}

function ScoreChip({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  if (value === null) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold"
        style={{
          background: 'rgba(148, 163, 184, 0.14)',
          color: 'var(--color-text-muted)',
          border: '1px solid rgba(148, 163, 184, 0.16)',
        }}
      >
        <span>{label}</span>
        <span>--</span>
      </span>
    );
  }

  const badgeStyle = getStatusBadgeStyle(value);

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold tabular-nums"
      style={{
        background: badgeStyle.background,
        color: badgeStyle.color,
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <span>{label}</span>
      <span>{value}</span>
    </span>
  );
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="relative h-6 w-11 rounded-full transition-colors"
      style={{ background: checked ? '#6366f1' : 'rgba(255,255,255,0.12)' }}
    >
      <span
        className="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform"
        style={{ left: checked ? '22px' : '2px' }}
      />
    </button>
  );
}

export default function ProductSelector({ config, onChange, onStartAnalysis, disabled }: Props) {
  const [search, setSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [missingEnglishOnly, setMissingEnglishOnly] = useState(false);
  const [sortBy, setSortBy] = useState<SortFieldKey>('name');
  const [sortDir, setSortDir] = useState<SortDirection>('asc');
  const [fieldScoreThresholds, setFieldScoreThresholds] = useState<FieldScoreThresholds>(
    DEFAULT_FIELD_SCORE_THRESHOLDS,
  );

  const listFieldOptions = FIELD_OPTIONS;
  const effectiveMissingEnglishOnly = missingEnglishOnly;
  const sortOptions: SortOption[] = [
    ...BASE_SORT_OPTIONS,
    ...listFieldOptions.map((field) => FIELD_SORT_OPTIONS[field.key]),
    { key: 'has_english_description', label: 'EN Durumu' },
  ];
  const activeFieldThresholdParams = listFieldOptions.reduce<Record<string, number>>((acc, field) => {
    acc[field.thresholdKey] = fieldScoreThresholds[field.thresholdKey];
    return acc;
  }, {});

  useEffect(() => {
    if (!sortOptions.some((option) => option.key === sortBy)) {
      setSortBy('name');
      setSortDir('asc');
    }
  }, [sortBy, sortOptions]);

  useEffect(() => {
    setPage(1);
  }, [
    pageSize,
    search,
    config.category_filter,
    config.score_threshold,
    effectiveMissingEnglishOnly,
    fieldScoreThresholds.title_score_threshold,
    fieldScoreThresholds.description_score_threshold,
    fieldScoreThresholds.english_description_score_threshold,
    fieldScoreThresholds.meta_score_threshold,
    fieldScoreThresholds.meta_desc_score_threshold,
    sortBy,
    sortDir,
  ]);

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
  });

  const { data, isLoading } = useQuery({
    queryKey: [
      'batchProducts',
      {
        page,
        pageSize,
        search,
        category: config.category_filter,
        scoreThreshold: config.score_threshold,
        missingEnglishOnly: effectiveMissingEnglishOnly,
        fieldThresholds: fieldScoreThresholds,
        sortBy,
        sortDir,
      },
    ],
    queryFn: () => fetchProducts(page, pageSize, effectiveMissingEnglishOnly ? 'missing_english' : 'all', {
      search,
      category: config.category_filter,
      score_threshold: config.score_threshold,
      ...activeFieldThresholdParams,
      sort_by: sortBy,
      sort_dir: sortDir,
    }),
  });

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 60_000,
  });
  const isDryRun = settings?.dry_run ?? true;

  const products: ProductWithScore[] = [...(data?.items ?? [])]
    .sort((left, right) => normalizeText(left.product.name).localeCompare(normalizeText(right.product.name), 'tr'))
    .sort((left, right) => {
      const leftValue = getSortValue(left, sortBy);
      const rightValue = getSortValue(right, sortBy);

      if (typeof leftValue === 'string' && typeof rightValue === 'string') {
        const compareResult = leftValue.localeCompare(rightValue, 'tr');
        return sortDir === 'asc' ? compareResult : -compareResult;
      }

      const compareResult = Number(leftValue) - Number(rightValue);
      return sortDir === 'asc' ? compareResult : -compareResult;
    });
  const totalCount = data?.total_count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const allPageIds = new Set(products.map((item) => item.product.id));
  const allSelected = products.length > 0 && products.every((item) => selectedIds.has(item.product.id));

  function setFieldThreshold(key: ScoreThresholdKey, rawValue: number) {
    const nextValue = Number.isFinite(rawValue) ? Math.max(0, Math.min(100, rawValue)) : 100;
    setFieldScoreThresholds((prev) => ({ ...prev, [key]: nextValue }));
  }

  function toggleAll() {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        allPageIds.forEach((id) => next.delete(id));
      } else {
        allPageIds.forEach((id) => next.add(id));
      }
      return next;
    });
  }

  function toggle(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-5">
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

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <div>
            <label className="mb-1 block text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              Ürün Ara
            </label>
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Ürün adı..."
              className="w-full rounded-lg px-3 py-2 text-[13px]"
              style={{
                background: 'var(--color-bg-primary)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>

          <div>
            <label className="mb-1 block text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              Kategori
            </label>
            <select
              value={config.category_filter}
              onChange={(event) => onChange({ ...config, category_filter: event.target.value })}
              className="w-full rounded-lg px-3 py-2 text-[13px]"
              style={{
                background: 'var(--color-bg-primary)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            >
              <option value="" style={{ background: '#0f172a', color: '#e5e7eb' }}>
                Tüm Kategoriler
              </option>
              {categories.map((category) => (
                <option key={category} value={category} style={{ background: '#0f172a', color: '#e5e7eb' }}>
                  {category}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              Toplam SEO Eşiği
            </label>
            <input
              type="number"
              min={0}
              max={100}
              value={config.score_threshold}
              onChange={(event) => onChange({ ...config, score_threshold: Number(event.target.value) })}
              className="w-full rounded-lg px-3 py-2 text-[13px]"
              style={{
                background: 'var(--color-bg-primary)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>
        </div>

        <div
          className="mt-4 flex flex-col gap-3 rounded-xl px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          style={{
            background: 'rgba(59, 130, 246, 0.08)',
            border: '1px solid rgba(59, 130, 246, 0.22)',
          }}
        >
          <div>
            <p className="text-[12px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Sadece EN açıklaması olmayan ürünler
            </p>
            <p className="mt-0.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              İngilizce açıklama alanı boş ürünleri ayrıca filtrele.
            </p>
          </div>
          <Toggle checked={missingEnglishOnly} onChange={setMissingEnglishOnly} />
        </div>

        {listFieldOptions.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                Alan Bazlı Skor Filtreleri
              </p>
              <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                100 = filtre kapalı
              </span>
            </div>
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              {listFieldOptions.map((field) => {
                const threshold = fieldScoreThresholds[field.thresholdKey];
                return (
                  <div
                    key={field.key}
                    className="rounded-xl p-3"
                    style={{
                      background: 'var(--color-bg-primary)',
                      border: '1px solid var(--color-border)',
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[12px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                          {field.label} Skoru
                        </p>
                        <p className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                          {field.hint}
                        </p>
                      </div>
                      {threshold < 100 && (
                        <button
                          type="button"
                          onClick={() => setFieldThreshold(field.thresholdKey, 100)}
                          className="rounded-lg px-2 py-1 text-[10px] font-medium"
                          style={{
                            background: 'rgba(99,102,241,0.12)',
                            border: '1px solid rgba(99,102,241,0.22)',
                          color: '#a5b4fc',
                        }}
                      >
                        Temizle
                      </button>
                      )}
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                        Maks
                      </span>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={threshold}
                        onChange={(event) => setFieldThreshold(field.thresholdKey, Number(event.target.value || 100))}
                        className="w-20 rounded-lg px-2.5 py-1.5 text-[12px]"
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid var(--color-border)',
                          color: 'var(--color-text-primary)',
                        }}
                      />
                      <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                        /100
                      </span>
                      <span
                        className="ml-auto text-[11px] font-medium"
                        style={{ color: threshold < 100 ? getScoreColor(threshold) : 'var(--color-text-muted)' }}
                      >
                        {threshold < 100 ? `${threshold} altı` : 'Kapalı'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

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

        <div className="mb-4">
          <p className="mb-2 text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Güncellenecek Alanlar
          </p>
          <div className="flex flex-wrap gap-2">
            {FIELD_OPTIONS.map((field) => {
              const active = config.target_fields.includes(field.key);
              return (
                <button
                  key={field.key}
                  type="button"
                  onClick={() => {
                    const nextFields = active
                      ? config.target_fields.filter((item) => item !== field.key)
                      : [...config.target_fields, field.key];
                    onChange({ ...config, target_fields: nextFields.length ? nextFields : [field.key] });
                  }}
                  className="rounded-full px-3 py-1.5 text-[12px] font-medium transition"
                  style={{
                    background: active ? 'rgba(99,102,241,0.15)' : 'var(--color-bg-primary)',
                    border: `1px solid ${active ? 'rgba(99,102,241,0.4)' : 'var(--color-border)'}`,
                    color: active ? '#a5b4fc' : 'var(--color-text-muted)',
                  }}
                >
                  {active ? '✓ ' : ''}
                  {field.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
            <input
              type="checkbox"
              checked={config.preserve_specs}
              onChange={(event) => onChange({ ...config, preserve_specs: event.target.checked })}
              className="rounded"
            />
            Teknik verileri koru (materyal, boyut, ağırlık)
          </label>
          <label className="flex items-center gap-2 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
            <input
              type="checkbox"
              checked={config.prevent_cannibalization}
              onChange={(event) => onChange({ ...config, prevent_cannibalization: event.target.checked })}
              className="rounded"
            />
            Kanibalizasyon önleme (LSI varyasyonları)
          </label>
        </div>

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
            onChange={(event) => onChange({ ...config, max_title_change_pct: Number(event.target.value) })}
            className="mt-1 w-full"
          />
        </div>
      </div>

      <div
        className="rounded-xl"
        style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
      >
        <div
          className="flex flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center"
          style={{ borderBottom: '1px solid var(--color-border)' }}
        >
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="rounded"
            />
            <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
              {selectedIds.size > 0
                ? `${selectedIds.size} ürün seçildi • ${totalCount} eşleşme`
                : `${totalCount} ürün listeleniyor`}
            </span>
          </div>

          <div className="flex flex-1 flex-wrap items-center gap-1.5 lg:justify-center">
            {config.score_threshold < 100 && (
              <ScoreChip label="Toplam Eşik" value={config.score_threshold} />
            )}
            {listFieldOptions.map((field) => {
              const threshold = fieldScoreThresholds[field.thresholdKey];
              if (threshold >= 100) {
                return null;
              }
              return (
                <ScoreChip
                  key={field.key}
                  label={`${field.badgeLabel} Eşik`}
                  value={threshold}
                />
              );
            })}
            {effectiveMissingEnglishOnly && (
              <span
                className="inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold"
                style={{
                  background: 'rgba(59,130,246,0.16)',
                  color: '#93c5fd',
                  border: '1px solid rgba(59,130,246,0.22)',
                }}
              >
                EN Eksik
              </span>
            )}
          </div>

          {totalCount > 0 && (
            <div className="flex flex-wrap items-center gap-3 lg:ml-auto">
              <label className="flex items-center gap-2 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                <span>Sıralama</span>
                <select
                  value={sortBy}
                  onChange={(event) => setSortBy(event.target.value as SortFieldKey)}
                  className="rounded-md px-2 py-1 text-[11px]"
                  style={{
                    background: 'var(--color-bg-primary)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text-primary)',
                    colorScheme: 'dark',
                  }}
                >
                  {sortOptions.map((option) => (
                    <option key={option.key} value={option.key} style={{ background: '#0f172a', color: '#e5e7eb' }}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'))}
                className="rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors"
                style={{
                  background: 'var(--color-bg-primary)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              >
                {sortDir === 'asc' ? 'Artan ↑' : 'Azalan ↓'}
              </button>
              <label className="flex items-center gap-2 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                <span>Listeleme</span>
                <select
                  value={pageSize}
                  onChange={(event) => setPageSize(Number(event.target.value))}
                  className="rounded-md px-2 py-1 text-[11px]"
                  style={{
                    background: 'var(--color-bg-primary)',
                    border: '1px solid var(--color-border)',
                    color: 'var(--color-text-primary)',
                    colorScheme: 'dark',
                  }}
                >
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={size} style={{ background: '#0f172a', color: '#e5e7eb' }}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
              <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                Sayfa {page}/{totalPages}
              </span>
            </div>
          )}
        </div>

        <div className="max-h-[520px] overflow-y-auto">
          {isLoading ? (
            <div className="p-8 text-center text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
              Ürünler yükleniyor...
            </div>
          ) : products.length === 0 ? (
            <div className="p-8 text-center text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
              Filtrelere uygun ürün bulunamadı.
            </div>
          ) : (
            products.map((item) => {
              const product = item.product;
              const totalScore = item.score?.total_score ?? null;
              const selected = selectedIds.has(product.id);
              const productHasEnglishDescription = hasEnglishDescription(product);

              return (
                <div
                  key={product.id}
                  className="cursor-pointer px-4 py-3 transition hover:bg-white/[0.02]"
                  style={{
                    borderBottom: '1px solid var(--color-border)',
                    background: selected ? 'rgba(99,102,241,0.08)' : 'transparent',
                  }}
                  onClick={() => toggle(product.id)}
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                    <div className="flex min-w-0 flex-1 items-start gap-3">
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggle(product.id)}
                        className="mt-1 rounded"
                        onClick={(event) => event.stopPropagation()}
                      />

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                            {product.name}
                          </p>
                          {!productHasEnglishDescription && (
                            <span
                              className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
                              style={{
                                background: 'rgba(59,130,246,0.14)',
                                color: '#93c5fd',
                                border: '1px solid rgba(59,130,246,0.2)',
                              }}
                            >
                              EN boş
                            </span>
                          )}
                        </div>

                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                          {product.category && <span>{product.category}</span>}
                          {product.sku && <span>SKU: {product.sku}</span>}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 lg:justify-end">
                      <ScoreChip label="Toplam" value={totalScore} />
                      {listFieldOptions.map((field) => (
                        <ScoreChip
                          key={field.key}
                          label={field.badgeLabel}
                          value={getFieldScore(item.score, field)}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {totalPages > 1 && (
          <div
            className="flex items-center justify-center gap-2 px-4 py-3"
            style={{ borderTop: '1px solid var(--color-border)' }}
          >
            <button
              disabled={page <= 1}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
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
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              className="rounded px-3 py-1 text-[12px] disabled:opacity-30"
              style={{ background: 'var(--color-bg-primary)', color: 'var(--color-text-secondary)' }}
            >
              Sonraki →
            </button>
          </div>
        )}
      </div>

      {isDryRun && (
        <div
          className="rounded-lg p-3"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}
        >
          <p className="text-[12px] font-semibold" style={{ color: '#f59e0b' }}>
            Güvenli Mod (DRY_RUN) Aktif
          </p>
          <p className="mt-0.5 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
            Değişiklikler yalnızca taslak olarak kaydedilecek. Canlı uygulamak için Ayarlar içinden DRY_RUN seçeneğini kapatın.
          </p>
        </div>
      )}

      <button
        disabled={disabled || selectedIds.size === 0}
        onClick={() => onStartAnalysis(Array.from(selectedIds))}
        className="w-full rounded-xl py-3.5 text-[14px] font-semibold text-white transition disabled:opacity-40"
        style={{ background: '#6366f1' }}
      >
        {selectedIds.size > 0 ? `${selectedIds.size} Ürünü Analiz Et` : 'Ürün Seçin'}
      </button>
    </div>
  );
}

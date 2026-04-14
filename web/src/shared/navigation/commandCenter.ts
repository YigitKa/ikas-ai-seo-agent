export const LOW_SCORE_THRESHOLD = 70;

const WORKSPACE_FILTERS = ['all', 'low_score', 'missing_english', 'pending', 'approved'] as const;
const PRODUCT_SORT_FIELDS = [
  'name',
  'category',
  'sku',
  'has_english_description',
  'total_score',
  'seo_score',
  'geo_score',
  'aeo_score',
  'title_score',
  'description_score',
  'english_description_score',
  'meta_score',
  'meta_desc_score',
] as const;
const CONTEXT_LABELS = {
  'attention-products': 'Dikkat gerektiren urunler',
  'quick-win': 'Hizli kazanim: dusuk skorlu urunler',
  'weakest-seo': 'SEO skoru zayif urunler',
  'weakest-geo': 'GEO skoru zayif urunler',
  'weakest-aeo': 'AEO skoru zayif urunler',
} as const;

export const WORKSPACE_PRESET_PARAM_KEYS = [
  'product',
  'filter',
  'sort_by',
  'sort_dir',
  'score_threshold',
  'seo_score_threshold',
  'geo_score_threshold',
  'aeo_score_threshold',
  'context',
] as const;

export const BATCH_PRESET_PARAM_KEYS = [
  'search',
  'category',
  'score_threshold',
  'title_score_threshold',
  'description_score_threshold',
  'english_description_score_threshold',
  'meta_score_threshold',
  'meta_desc_score_threshold',
  'missing_english',
  'sort_by',
  'sort_dir',
  'context',
] as const;

export type WorkspaceFilterTab = (typeof WORKSPACE_FILTERS)[number];
export type ProductSortField = (typeof PRODUCT_SORT_FIELDS)[number];
export type ProductSortDirection = 'asc' | 'desc';
export type CommandCenterContextKey = keyof typeof CONTEXT_LABELS;

export interface WorkspaceRoutePreset {
  hasPreset: boolean;
  productId: string | null;
  filter: WorkspaceFilterTab;
  sortBy: ProductSortField | null;
  sortDir: ProductSortDirection;
  scoreThreshold: number | null;
  seoScoreThreshold: number | null;
  geoScoreThreshold: number | null;
  aeoScoreThreshold: number | null;
  contextKey: CommandCenterContextKey | null;
  contextLabel: string | null;
}

export interface BatchRoutePreset {
  hasPreset: boolean;
  search: string;
  categoryFilter: string;
  scoreThreshold: number | null;
  titleScoreThreshold: number | null;
  descriptionScoreThreshold: number | null;
  englishDescriptionScoreThreshold: number | null;
  metaScoreThreshold: number | null;
  metaDescScoreThreshold: number | null;
  missingEnglishOnly: boolean;
  sortBy: ProductSortField | null;
  sortDir: ProductSortDirection;
  contextKey: CommandCenterContextKey | null;
  contextLabel: string | null;
}

function sanitizeText(value: string | null | undefined) {
  return value?.trim() || '';
}

function parsePercent(value: string | null) {
  if (!value) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.max(0, Math.min(100, Math.round(parsed)));
}

function parseFilter(value: string | null): WorkspaceFilterTab {
  return WORKSPACE_FILTERS.includes((value || '') as WorkspaceFilterTab)
    ? (value as WorkspaceFilterTab)
    : 'all';
}

function parseSortField(value: string | null): ProductSortField | null {
  return PRODUCT_SORT_FIELDS.includes((value || '') as ProductSortField)
    ? (value as ProductSortField)
    : null;
}

function parseSortDirection(value: string | null): ProductSortDirection {
  return value === 'desc' ? 'desc' : 'asc';
}

function parseContextKey(value: string | null): CommandCenterContextKey | null {
  return value && value in CONTEXT_LABELS
    ? (value as CommandCenterContextKey)
    : null;
}

function parseBooleanFlag(value: string | null) {
  return value === '1' || value?.toLowerCase() === 'true';
}

function buildUrl(pathname: string, params: URLSearchParams) {
  const qs = params.toString();
  return qs ? `${pathname}?${qs}` : pathname;
}

export function buildAttentionWorkspaceUrl(productId?: string) {
  const params = new URLSearchParams({
    filter: 'low_score',
    sort_by: 'total_score',
    sort_dir: 'asc',
    context: 'attention-products',
  });

  if (sanitizeText(productId)) {
    params.set('product', sanitizeText(productId));
  }

  return buildUrl('/workspace', params);
}

export function buildWeakestPillarWorkspaceUrl(pillar: 'seo' | 'geo' | 'aeo') {
  const params = new URLSearchParams({
    sort_by: `${pillar}_score`,
    sort_dir: 'asc',
    context: `weakest-${pillar}`,
    [`${pillar}_score_threshold`]: String(LOW_SCORE_THRESHOLD),
  });

  return buildUrl('/workspace', params);
}

export function buildQuickWinBatchUrl() {
  const params = new URLSearchParams({
    score_threshold: String(LOW_SCORE_THRESHOLD),
    sort_by: 'total_score',
    sort_dir: 'asc',
    context: 'quick-win',
  });

  return buildUrl('/batch', params);
}

export function parseWorkspacePreset(searchParams: URLSearchParams): WorkspaceRoutePreset {
  const contextKey = parseContextKey(searchParams.get('context'));

  return {
    hasPreset: WORKSPACE_PRESET_PARAM_KEYS.some((key) => searchParams.has(key)),
    productId: sanitizeText(searchParams.get('product')) || null,
    filter: parseFilter(searchParams.get('filter')),
    sortBy: parseSortField(searchParams.get('sort_by')),
    sortDir: parseSortDirection(searchParams.get('sort_dir')),
    scoreThreshold: parsePercent(searchParams.get('score_threshold')),
    seoScoreThreshold: parsePercent(searchParams.get('seo_score_threshold')),
    geoScoreThreshold: parsePercent(searchParams.get('geo_score_threshold')),
    aeoScoreThreshold: parsePercent(searchParams.get('aeo_score_threshold')),
    contextKey,
    contextLabel: contextKey ? CONTEXT_LABELS[contextKey] : null,
  };
}

export function parseBatchPreset(searchParams: URLSearchParams): BatchRoutePreset {
  const contextKey = parseContextKey(searchParams.get('context'));

  return {
    hasPreset: BATCH_PRESET_PARAM_KEYS.some((key) => searchParams.has(key)),
    search: sanitizeText(searchParams.get('search')),
    categoryFilter: sanitizeText(searchParams.get('category')),
    scoreThreshold: parsePercent(searchParams.get('score_threshold')),
    titleScoreThreshold: parsePercent(searchParams.get('title_score_threshold')),
    descriptionScoreThreshold: parsePercent(searchParams.get('description_score_threshold')),
    englishDescriptionScoreThreshold: parsePercent(searchParams.get('english_description_score_threshold')),
    metaScoreThreshold: parsePercent(searchParams.get('meta_score_threshold')),
    metaDescScoreThreshold: parsePercent(searchParams.get('meta_desc_score_threshold')),
    missingEnglishOnly: parseBooleanFlag(searchParams.get('missing_english')),
    sortBy: parseSortField(searchParams.get('sort_by')),
    sortDir: parseSortDirection(searchParams.get('sort_dir')),
    contextKey,
    contextLabel: contextKey ? CONTEXT_LABELS[contextKey] : null,
  };
}

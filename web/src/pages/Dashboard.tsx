import { useCallback, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  fetchProducts,
  getProduct,
  getSettings,
  syncProductsFromIkas,
} from '../api/client';
import ChatPanel from '../components/ChatPanel';
import DashboardEmptyState from '../components/dashboard/DashboardEmptyState';
import DashboardSidebar from '../components/dashboard/DashboardSidebar';
import GscPanel from '../components/dashboard/GscPanel';
import type { FilterTab } from '../components/dashboard/constants';
import { buildIkasProductUrl } from '../components/dashboard/productUrl';
import {
  WORKSPACE_PRESET_PARAM_KEYS,
  parseWorkspacePreset,
  type ProductSortDirection,
  type ProductSortField,
} from '../shared/navigation/commandCenter';
import AppHeader from '../shared/ui/AppHeader';
import { useToast } from '../shared/ui/Toast';
import { EnterpriseButton, EnterpriseSurface } from '../shared/ui/EnterprisePrimitives';

interface WorkspaceListState {
  sortBy: ProductSortField;
  sortDir: ProductSortDirection;
  scoreThreshold: number;
  seoScoreThreshold: number;
  geoScoreThreshold: number;
  aeoScoreThreshold: number;
}

const DEFAULT_WORKSPACE_LIST_STATE: WorkspaceListState = {
  sortBy: 'name',
  sortDir: 'asc',
  scoreThreshold: 100,
  seoScoreThreshold: 100,
  geoScoreThreshold: 100,
  aeoScoreThreshold: 100,
};

export default function Dashboard() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialPreset = parseWorkspacePreset(searchParams);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<FilterTab>(initialPreset.filter);
  const [selectedId, setSelectedId] = useState<string | null>(initialPreset.productId);
  const [listState, setListState] = useState<WorkspaceListState>({
    sortBy: initialPreset.sortBy ?? DEFAULT_WORKSPACE_LIST_STATE.sortBy,
    sortDir: initialPreset.sortDir,
    scoreThreshold: initialPreset.scoreThreshold ?? DEFAULT_WORKSPACE_LIST_STATE.scoreThreshold,
    seoScoreThreshold: initialPreset.seoScoreThreshold ?? DEFAULT_WORKSPACE_LIST_STATE.seoScoreThreshold,
    geoScoreThreshold: initialPreset.geoScoreThreshold ?? DEFAULT_WORKSPACE_LIST_STATE.geoScoreThreshold,
    aeoScoreThreshold: initialPreset.aeoScoreThreshold ?? DEFAULT_WORKSPACE_LIST_STATE.aeoScoreThreshold,
  });
  const [commandContextLabel, setCommandContextLabel] = useState<string | null>(initialPreset.contextLabel);

  // ── Switch guard ──────────────────────────────────────────────────────────
  /** Set while a ChatPanel request is in flight. Stored as a ref so that the
   *  stable `handleLoadingChange` callback always reads the latest value. */
  const chatIsLoadingRef = useRef(false);

  /** Product ID the user clicked while a request was in progress. Showing the
   *  modal means we haven't committed to a switch yet. */
  const [pendingClickId, setPendingClickId] = useState<string | null>(null);

  /** Product to switch to once the current request finishes ("analiz bitince
   *  gec"). Stored both as state (drives banner re-render) and as a ref (read
   *  inside the stable loadingChange callback). */
  const [afterLoadSwitchId, setAfterLoadSwitchId] = useState<string | null>(null);
  const afterLoadSwitchIdRef = useRef<string | null>(null);
  afterLoadSwitchIdRef.current = afterLoadSwitchId;
  // ─────────────────────────────────────────────────────────────────────────

  const settingsQ = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
    staleTime: 5 * 60 * 1000,
  });

  const productsQ = useQuery({
    queryKey: ['products', page, filter, listState],
    queryFn: () => fetchProducts(page, 50, filter, {
      score_threshold: listState.scoreThreshold,
      seo_score_threshold: listState.seoScoreThreshold,
      geo_score_threshold: listState.geoScoreThreshold,
      aeo_score_threshold: listState.aeoScoreThreshold,
      sort_by: listState.sortBy,
      sort_dir: listState.sortDir,
    }),
  });

  const detailQ = useQuery({
    queryKey: ['product', selectedId],
    queryFn: () => getProduct(selectedId!),
    enabled: !!selectedId,
  });

  const syncProductsMut = useMutation({
    mutationFn: syncProductsFromIkas,
    onSuccess: (data) => {
      toast.success(`${data.fetched_count}/${data.total_count} ürün ikas'tan senkronlandı.`);
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product'] });
    },
    onError: () => {
      toast.error('Senkronizasyon başarısız. Bağlantınızı ve ikas ayarlarınızı kontrol edin.');
    },
  });

  const totalPages = productsQ.data
    ? Math.ceil(productsQ.data.total_count / productsQ.data.limit)
    : 1;

  const selectedProduct = detailQ.data?.product;
  const selectedScore = detailQ.data?.score ?? null;
  const requestedSkillSlug = (searchParams.get('skill') || '').trim();
  const productDetailUrl =
    selectedProduct && settingsQ.data?.store_name
      ? buildIkasProductUrl(
          settingsQ.data.store_name,
          selectedProduct.slug,
          selectedProduct.id,
          selectedProduct.name,
        )
      : '';

  useEffect(() => {
    const preset = parseWorkspacePreset(searchParams);
    if (preset.hasPreset) {
      setFilter(preset.filter);
      setPage(1);
      setSelectedId(preset.productId);
      setListState({
        sortBy: preset.sortBy ?? DEFAULT_WORKSPACE_LIST_STATE.sortBy,
        sortDir: preset.sortDir,
        scoreThreshold: preset.scoreThreshold ?? DEFAULT_WORKSPACE_LIST_STATE.scoreThreshold,
        seoScoreThreshold: preset.seoScoreThreshold ?? DEFAULT_WORKSPACE_LIST_STATE.seoScoreThreshold,
        geoScoreThreshold: preset.geoScoreThreshold ?? DEFAULT_WORKSPACE_LIST_STATE.geoScoreThreshold,
        aeoScoreThreshold: preset.aeoScoreThreshold ?? DEFAULT_WORKSPACE_LIST_STATE.aeoScoreThreshold,
      });
      setCommandContextLabel(preset.contextLabel);
    }

    if (!requestedSkillSlug && !preset.hasPreset) return;

    const nextParams = new URLSearchParams(searchParams);
    let shouldReplace = false;
    if (requestedSkillSlug) {
      nextParams.delete('skill');
      shouldReplace = true;
    }
    for (const key of WORKSPACE_PRESET_PARAM_KEYS) {
      if (!nextParams.has(key)) continue;
      nextParams.delete(key);
      shouldReplace = true;
    }
    if (!shouldReplace) return;
    setSearchParams(nextParams, { replace: true });
  }, [requestedSkillSlug, searchParams, setSearchParams]);

  // ── Sidebar selection with switch guard ───────────────────────────────────
  const handleSelectProduct = (id: string) => {
    if (chatIsLoadingRef.current && selectedId && selectedId !== id) {
      setPendingClickId(id);
      return;
    }
    setSelectedId(id);
  };

  /** Stable callback passed to ChatPanel — reads ref values to avoid stale closures. */
  const handleLoadingChange = useCallback((isLoading: boolean) => {
    chatIsLoadingRef.current = isLoading;

    if (!isLoading && afterLoadSwitchIdRef.current) {
      const nextId = afterLoadSwitchIdRef.current;
      afterLoadSwitchIdRef.current = null;
      setAfterLoadSwitchId(null);
      setSelectedId(nextId);
    }
  }, []);

  // Banner product name (shown while waiting for load to finish)
  const bannerProductName = afterLoadSwitchId && productsQ.data
    ? (productsQ.data.items.find((i) => i.product.id === afterLoadSwitchId)?.product.name ??
        'diger urun')
    : null;
  // ─────────────────────────────────────────────────────────────────────────

  const handleFilterChange = (nextFilter: FilterTab) => {
    setCommandContextLabel(null);
    setListState(DEFAULT_WORKSPACE_LIST_STATE);
    setFilter(nextFilter);
    setPage(1);
  };

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
      <AppHeader
        title="AI destekli SEO Asistanı"
        description="Urun kataloğunu tarayin, secili urunlerde AI destekli SEO akisini denetimli sekilde ilerletin."
        eyebrow={{ label: 'Dashboard', tone: 'primary' }}
        breadcrumbs={[{ label: 'Dashboard' }]}
        meta={[
          {
            label: 'Katalog',
            value:
              typeof productsQ.data?.total_count === 'number'
                ? `${productsQ.data.total_count} urun`
                : 'Veri bekleniyor',
          },
          {
            label: 'Secili urun',
            value: selectedProduct?.name ?? 'Urun secilmedi',
            tone: selectedProduct ? 'success' : 'neutral',
          },
        ]}
        actions={(
          <EnterpriseButton
            onClick={() => syncProductsMut.mutate()}
            disabled={syncProductsMut.isPending}
            tone="primary"
            className="flex items-center gap-1.5"
          >
            {syncProductsMut.isPending ? (
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
            ) : (
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            )}
            {syncProductsMut.isPending ? 'Senkronlaniyor...' : 'Tum urunleri senkronla'}
          </EnterpriseButton>
        )}
        wrapperClassName="px-4"
        showPanel={false}
      />

      <div className="flex flex-1 overflow-hidden">
        <DashboardSidebar
          items={productsQ.data?.items ?? []}
          selectedId={selectedId}
          isLoading={productsQ.isLoading}
          filter={filter}
          contextLabel={commandContextLabel}
          page={page}
          totalPages={totalPages}
          totalCount={productsQ.data?.total_count}
          isSyncing={syncProductsMut.isPending}
          onSelect={handleSelectProduct}
          onFilterChange={handleFilterChange}
          onPageChange={setPage}
          onSync={() => syncProductsMut.mutate()}
        />

        <main className="flex flex-1 overflow-hidden">
          <section className="min-w-0 flex flex-1 flex-col overflow-hidden p-4">

            {bannerProductName && (
              <EnterpriseSurface
                className="mb-3 flex items-center gap-2 px-4 py-2.5 text-sm"
                style={{
                  background: 'linear-gradient(135deg, var(--color-border-primary), var(--tint-info-soft))',
                  border: '1px solid var(--color-border-primary)',
                  color: 'var(--color-primary-light)',
                }}
              >
                <svg
                  className="h-4 w-4 flex-shrink-0 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                <span>
                  Analiz tamamlaninca <strong>{bannerProductName}</strong> urününe otomatik
                  gecilecek.
                </span>
              </EnterpriseSurface>
            )}

            {!selectedProduct && (
              <DashboardEmptyState requestedSkillSlug={requestedSkillSlug || undefined} />
            )}

            <div className="min-h-0 flex flex-1 flex-col gap-5 overflow-hidden">
              <div className="min-h-0 flex-1">
                <ChatPanel
                  productId={selectedId ?? undefined}
                  productName={selectedProduct?.name}
                  productCategory={selectedProduct?.category}
                  seoScore={selectedScore?.total_score ?? null}
                  product={selectedProduct ?? null}
                  score={selectedScore}
                  productDetailUrl={productDetailUrl}
                  onLoadingChange={handleLoadingChange}
                  requestedSkillSlug={requestedSkillSlug || undefined}
                />
              </div>
            </div>
          </section>

          {/* ── GSC Panel (sağ kenar — sadece xl+ ekranlarda) ──────────────── */}
          {selectedProduct && (
            <aside
              className="enterprise-panel-divider hidden xl:flex w-[288px] shrink-0 flex-col overflow-y-auto p-4"
              style={{
                background: 'linear-gradient(180deg, var(--surface-code), var(--surface-panel))',
                borderLeft: '1px solid var(--color-border)',
              }}
            >
              <GscPanel product={selectedProduct} />
            </aside>
          )}
        </main>
      </div>

      {/* ── Product-switch confirmation modal ─────────────────────────────── */}
      {pendingClickId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'var(--color-overlay-dark)', backdropFilter: 'blur(4px)' }}
        >
          <EnterpriseSurface
            className="mx-4 w-full max-w-sm p-6"
            style={{
              background: 'linear-gradient(180deg, var(--surface-code), var(--surface-code))',
              border: '1px solid var(--color-border-strong)',
              boxShadow: '0 24px 48px rgba(2,6,23,0.65)',
            }}
          >
            <div className="mb-1 flex items-center gap-2">
              <svg
                className="h-5 w-5 flex-shrink-0"
                style={{ color: 'var(--color-icon-warning)' }}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                />
              </svg>
              <h2
                className="text-[15px] font-semibold"
                style={{ color: 'var(--color-text-primary)' }}
              >
                Devam eden bir analiz var
              </h2>
            </div>
            <p
              className="mb-5 text-[13px] leading-relaxed"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Bu urun icin AI analizi henuz tamamlanmadi. Ne yapmak istersiniz?
            </p>

            <div className="flex flex-col gap-2">
              {/* Stop and switch immediately */}
              <EnterpriseButton
                onClick={() => {
                  const nextId = pendingClickId;
                  setPendingClickId(null);
                  setSelectedId(nextId);
                }}
                tone="danger"
                className="w-full"
              >
                Durdur ve Gec
              </EnterpriseButton>

              {/* Wait for the response then switch */}
              <EnterpriseButton
                onClick={() => {
                  setAfterLoadSwitchId(pendingClickId);
                  afterLoadSwitchIdRef.current = pendingClickId;
                  setPendingClickId(null);
                }}
                tone="primary"
                className="w-full"
              >
                Analiz Bitince Gec
              </EnterpriseButton>

              {/* Stay on current product */}
              <EnterpriseButton
                onClick={() => setPendingClickId(null)}
                tone="neutral"
                className="w-full"
              >
                Iptal
              </EnterpriseButton>
            </div>
          </EnterpriseSurface>
        </div>
      )}
    </div>
  );
}

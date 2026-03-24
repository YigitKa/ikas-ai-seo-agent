import { useCallback, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchProducts,
  generateLlmsTxt,
  getProduct,
  getSettings,
  resetLocalProductData,
  syncProductsFromIkas,
} from '../api/client';
import ChatPanel from '../components/ChatPanel';
import DashboardEmptyState from '../components/dashboard/DashboardEmptyState';
import DashboardHeader from '../components/dashboard/DashboardHeader';
import DashboardSidebar from '../components/dashboard/DashboardSidebar';
import type { FilterTab } from '../components/dashboard/constants';
import { buildIkasProductUrl } from '../components/dashboard/productUrl';

export default function Dashboard() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<FilterTab>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);

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
    queryKey: ['products', page, filter],
    queryFn: () => fetchProducts(page, 50, filter),
  });

  const detailQ = useQuery({
    queryKey: ['product', selectedId],
    queryFn: () => getProduct(selectedId!),
    enabled: !!selectedId,
  });

  const syncProductsMut = useMutation({
    mutationFn: syncProductsFromIkas,
    onSuccess: (data) => {
      alert(`${data.fetched_count}/${data.total_count} urun ikas'tan senkronlandi.`);
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product'] });
    },
  });

  const resetLocalDataMut = useMutation({
    mutationFn: resetLocalProductData,
    onSuccess: (data) => {
      setSelectedId(null);
      alert(
        `${data.products_deleted} urun, ${data.scores_deleted} skor, ${data.suggestions_deleted} oneri ve ${data.logs_deleted} log silindi.`,
      );
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product'] });
      queryClient.invalidateQueries({ queryKey: ['suggestions'] });
    },
  });

  const llmsTxtMut = useMutation({
    mutationFn: generateLlmsTxt,
    onSuccess: (text) => {
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'llms.txt';
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  const totalPages = productsQ.data
    ? Math.ceil(productsQ.data.total_count / productsQ.data.limit)
    : 1;

  const selectedProduct = detailQ.data?.product;
  const selectedScore = detailQ.data?.score ?? null;
  const productDetailUrl =
    selectedProduct && settingsQ.data?.store_name
      ? buildIkasProductUrl(
          settingsQ.data.store_name,
          selectedProduct.slug,
          selectedProduct.id,
          selectedProduct.name,
        )
      : '';

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
    setFilter(nextFilter);
    setPage(1);
  };

  const handleResetLocalData = () => {
    if (window.confirm('Local urun cache veritabani sifirlansin mi? Bu islem geri alinamaz.')) {
      resetLocalDataMut.mutate();
    }
  };

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
      <DashboardHeader
        totalCount={productsQ.data?.total_count}
        syncPending={syncProductsMut.isPending}
        resetPending={resetLocalDataMut.isPending}
        llmsTxtPending={llmsTxtMut.isPending}
        onSync={() => syncProductsMut.mutate()}
        onReset={handleResetLocalData}
        onDownloadLlmsTxt={() => llmsTxtMut.mutate()}
      />

      <div className="flex flex-1 overflow-hidden">
        <DashboardSidebar
          items={productsQ.data?.items ?? []}
          selectedId={selectedId}
          isLoading={productsQ.isLoading}
          filter={filter}
          page={page}
          totalPages={totalPages}
          onSelect={handleSelectProduct}
          onFilterChange={handleFilterChange}
          onPageChange={setPage}
        />

        <main className="flex flex-1 overflow-hidden">
          {selectedId && selectedProduct ? (
            <section className="min-w-0 flex flex-1 flex-col overflow-hidden p-6">
              {/* "Analiz bitince gec" banner */}
              {bannerProductName && (
                <div
                  className="mb-3 flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm"
                  style={{
                    background: 'rgba(99,102,241,0.12)',
                    border: '1px solid rgba(99,102,241,0.3)',
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
                </div>
              )}

              <div className="min-h-0 flex flex-1 flex-col gap-5 overflow-hidden">
                <div className="min-h-0 flex-1">
                  <ChatPanel
                    productId={selectedId}
                    productName={selectedProduct.name}
                    productCategory={selectedProduct.category}
                    seoScore={selectedScore?.total_score ?? null}
                    product={selectedProduct}
                    score={selectedScore}
                    productDetailUrl={productDetailUrl}
                    onLoadingChange={handleLoadingChange}
                  />
                </div>
              </div>
            </section>
          ) : (
            <DashboardEmptyState />
          )}
        </main>
      </div>

      {/* ── Product-switch confirmation modal ─────────────────────────────── */}
      {pendingClickId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
        >
          <div
            className="mx-4 w-full max-w-sm rounded-2xl p-6"
            style={{
              background: 'var(--color-bg-surface)',
              border: '1px solid rgba(148,163,184,0.18)',
              boxShadow: '0 24px 48px rgba(2,6,23,0.6)',
            }}
          >
            <div className="mb-1 flex items-center gap-2">
              <svg
                className="h-5 w-5 flex-shrink-0"
                style={{ color: '#fbbf24' }}
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
              <button
                onClick={() => {
                  const nextId = pendingClickId;
                  setPendingClickId(null);
                  setSelectedId(nextId);
                }}
                className="w-full rounded-xl px-4 py-2.5 text-[13px] font-medium transition-colors hover:opacity-80"
                style={{
                  background: 'rgba(239,68,68,0.12)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  color: '#f87171',
                }}
              >
                Durdur ve Gec
              </button>

              {/* Wait for the response then switch */}
              <button
                onClick={() => {
                  setAfterLoadSwitchId(pendingClickId);
                  afterLoadSwitchIdRef.current = pendingClickId;
                  setPendingClickId(null);
                }}
                className="w-full rounded-xl px-4 py-2.5 text-[13px] font-medium transition-colors hover:opacity-80"
                style={{
                  background: 'rgba(99,102,241,0.12)',
                  border: '1px solid rgba(99,102,241,0.3)',
                  color: 'var(--color-primary-light)',
                }}
              >
                Analiz Bitince Gec
              </button>

              {/* Stay on current product */}
              <button
                onClick={() => setPendingClickId(null)}
                className="w-full rounded-xl px-4 py-2.5 text-[13px] font-medium transition-colors hover:opacity-80"
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(148,163,184,0.15)',
                  color: 'var(--color-text-muted)',
                }}
              >
                Iptal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

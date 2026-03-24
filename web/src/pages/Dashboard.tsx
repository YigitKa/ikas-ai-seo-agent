import { useCallback, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchProducts,
  getProduct,
  getSettings,
  syncProductsFromIkas,
} from '../api/client';
import ChatPanel from '../components/ChatPanel';
import DashboardEmptyState from '../components/dashboard/DashboardEmptyState';
import DashboardHeader from '../components/dashboard/DashboardHeader';
import DashboardSidebar from '../components/dashboard/DashboardSidebar';
import type { FilterTab } from '../components/dashboard/constants';
import { buildIkasProductUrl } from '../components/dashboard/productUrl';
import { useToast } from '../shared/ui/Toast';
import { EnterpriseButton, EnterpriseSurface } from '../shared/ui/EnterprisePrimitives';

export default function Dashboard() {
  const queryClient = useQueryClient();
  const toast = useToast();
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

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
      <DashboardHeader
        totalCount={productsQ.data?.total_count}
        syncPending={syncProductsMut.isPending}
        onSync={() => syncProductsMut.mutate()}
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
                <EnterpriseSurface
                  className="mb-3 flex items-center gap-2 px-4 py-2.5 text-sm"
                  style={{
                    background: 'linear-gradient(135deg, rgba(99,102,241,0.22), rgba(59,130,246,0.14))',
                    border: '1px solid rgba(99,102,241,0.38)',
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
          <EnterpriseSurface
            className="mx-4 w-full max-w-sm p-6"
            style={{
              background: 'linear-gradient(180deg, rgba(15,23,42,0.95), rgba(2,6,23,0.92))',
              border: '1px solid rgba(148,163,184,0.22)',
              boxShadow: '0 24px 48px rgba(2,6,23,0.65)',
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

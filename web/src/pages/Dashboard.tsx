import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  applyApproved,
  fetchProducts,
  getProduct,
  getSettings,
  resetLocalProductData,
  syncProductsFromIkas,
} from '../api/client';
import DashboardDetail from '../components/dashboard/DashboardDetail';
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

  const applyMut = useMutation({
    mutationFn: applyApproved,
    onSuccess: (data) => {
      alert(`${data.applied}/${data.total} oneri ikas'a uygulandi.`);
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['suggestions'] });
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
        applyPending={applyMut.isPending}
        onSync={() => syncProductsMut.mutate()}
        onReset={handleResetLocalData}
        onApply={() => applyMut.mutate()}
      />

      <div className="flex flex-1 overflow-hidden">
        <DashboardSidebar
          items={productsQ.data?.items ?? []}
          selectedId={selectedId}
          isLoading={productsQ.isLoading}
          filter={filter}
          page={page}
          totalPages={totalPages}
          onSelect={setSelectedId}
          onFilterChange={handleFilterChange}
          onPageChange={setPage}
        />

        <main className="flex flex-1 overflow-hidden">
          {selectedId && selectedProduct ? (
            <DashboardDetail
              productId={selectedId}
              product={selectedProduct}
              score={selectedScore}
              productDetailUrl={productDetailUrl}
            />
          ) : (
            <DashboardEmptyState />
          )}
        </main>
      </div>
    </div>
  );
}

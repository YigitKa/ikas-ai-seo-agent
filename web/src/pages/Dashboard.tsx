import { useCallback, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ProductTable from '../components/ProductTable';
import ScoreCard from '../components/ScoreCard';
import DiffViewer from '../components/DiffViewer';
import ChatPanel from '../components/ChatPanel';
import {
  fetchProducts,
  fetchProductsFromIkas,
  getProduct,
  generateSuggestion,
  generateFieldRewrite,
  getSuggestions,
  approveSuggestion,
  rejectSuggestion,
  applyApproved,
} from '../api/client';
import type { SeoSuggestion } from '../types';

type FilterTab = 'all' | 'low_score' | 'pending' | 'approved';

const FILTER_LABELS: Record<FilterTab, string> = {
  all: 'Tumu',
  low_score: 'Dusuk Skor',
  pending: 'Bekleyen',
  approved: 'Onaylanan',
};

export default function Dashboard() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<FilterTab>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rewritingField, setRewritingField] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);

  // ── Queries ───────────────────────────────────────────────────────────────
  const productsQ = useQuery({
    queryKey: ['products', page, filter],
    queryFn: () => fetchProducts(page, 50, filter),
  });

  const detailQ = useQuery({
    queryKey: ['product', selectedId],
    queryFn: () => getProduct(selectedId!),
    enabled: !!selectedId,
  });

  const suggestionsQ = useQuery({
    queryKey: ['suggestions', selectedId],
    queryFn: () => getSuggestions(selectedId!),
    enabled: !!selectedId,
  });

  const latestSuggestion: SeoSuggestion | null =
    suggestionsQ.data?.[0] ?? null;

  // ── Mutations ─────────────────────────────────────────────────────────────
  const fetchMut = useMutation({
    mutationFn: () => fetchProductsFromIkas(page, 50),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  });

  const rewriteMut = useMutation({
    mutationFn: (productId: string) => generateSuggestion(productId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['suggestions', selectedId] });
    },
  });

  const fieldRewriteMut = useMutation({
    mutationFn: ({ productId, field }: { productId: string; field: string }) =>
      generateFieldRewrite(productId, field),
    onSuccess: () => {
      setRewritingField(null);
      qc.invalidateQueries({ queryKey: ['suggestions', selectedId] });
    },
    onError: () => setRewritingField(null),
  });

  const approveMut = useMutation({
    mutationFn: (productId: string) => approveSuggestion(productId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['suggestions', selectedId] }),
  });

  const rejectMut = useMutation({
    mutationFn: (productId: string) => rejectSuggestion(productId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['suggestions', selectedId] }),
  });

  const applyMut = useMutation({
    mutationFn: () => applyApproved(),
    onSuccess: (data) => {
      alert(`${data.applied}/${data.total} oneri ikas'a uygulandi.`);
      qc.invalidateQueries({ queryKey: ['products'] });
    },
  });

  const handleRewriteField = useCallback(
    (field: string) => {
      if (!selectedId) return;
      setRewritingField(field);
      fieldRewriteMut.mutate({ productId: selectedId, field });
    },
    [selectedId, fieldRewriteMut],
  );

  const totalPages = productsQ.data
    ? Math.ceil(productsQ.data.total_count / productsQ.data.limit)
    : 1;

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100">
      {/* ── Left: Product list ──────────────────────────────────── */}
      <div className="flex w-[420px] flex-col border-r border-gray-700">
        {/* Toolbar */}
        <div className="border-b border-gray-700 p-3 space-y-2">
          <div className="flex gap-2">
            <button
              onClick={() => fetchMut.mutate()}
              disabled={fetchMut.isPending}
              className="flex-1 rounded-lg bg-blue-600 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
            >
              {fetchMut.isPending ? 'Cekiliyor...' : 'Urunleri Cek'}
            </button>
            <button
              onClick={() => applyMut.mutate()}
              disabled={applyMut.isPending}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-500 disabled:opacity-50"
            >
              Uygula
            </button>
          </div>

          {/* Filter tabs */}
          <div className="flex gap-1">
            {(Object.keys(FILTER_LABELS) as FilterTab[]).map((key) => (
              <button
                key={key}
                onClick={() => {
                  setFilter(key);
                  setPage(1);
                }}
                className={`rounded px-2.5 py-1 text-xs font-medium transition ${
                  filter === key
                    ? 'bg-blue-600/30 text-blue-300'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {FILTER_LABELS[key]}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          {productsQ.isLoading ? (
            <div className="flex h-40 items-center justify-center text-sm text-gray-500">
              Yukleniyor...
            </div>
          ) : (
            <ProductTable
              items={productsQ.data?.items ?? []}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-gray-700 px-3 py-2 text-xs text-gray-400">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded px-2 py-1 hover:text-white disabled:opacity-30"
            >
              Onceki
            </button>
            <span>
              {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded px-2 py-1 hover:text-white disabled:opacity-30"
            >
              Sonraki
            </button>
          </div>
        )}
      </div>

      {/* ── Center: Detail ──────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {selectedId && detailQ.data ? (
          <>
            {/* Product header */}
            <div className="flex items-center justify-between border-b border-gray-700 px-5 py-3">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  {detailQ.data.product.name}
                </h2>
                <p className="text-xs text-gray-500">
                  {detailQ.data.product.category || 'Kategori yok'} &middot;{' '}
                  {detailQ.data.product.sku || 'SKU yok'}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => rewriteMut.mutate(selectedId)}
                  disabled={rewriteMut.isPending}
                  className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-purple-500 disabled:opacity-50"
                >
                  {rewriteMut.isPending ? 'Yaziliyor...' : 'Tumunu Yeniden Yaz'}
                </button>
                {latestSuggestion?.status === 'pending' && (
                  <>
                    <button
                      onClick={() => approveMut.mutate(selectedId)}
                      className="rounded-lg bg-green-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-green-500"
                    >
                      Onayla
                    </button>
                    <button
                      onClick={() => rejectMut.mutate(selectedId)}
                      className="rounded-lg bg-red-600/80 px-3 py-2 text-sm font-medium text-white transition hover:bg-red-500"
                    >
                      Reddet
                    </button>
                  </>
                )}
                <button
                  onClick={() => setShowChat((v) => !v)}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                    showChat
                      ? 'border-blue-500 bg-blue-600/20 text-blue-300'
                      : 'border-gray-600 text-gray-400 hover:text-white'
                  }`}
                >
                  Chat
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="flex flex-1 overflow-hidden">
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {detailQ.data.score && <ScoreCard score={detailQ.data.score} />}
                <DiffViewer
                  product={detailQ.data.product}
                  suggestion={latestSuggestion}
                  onRewriteField={handleRewriteField}
                  rewritingField={rewritingField}
                />
              </div>

              {showChat && (
                <div className="w-[360px] border-l border-gray-700 p-3">
                  <ChatPanel productId={selectedId} />
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-gray-500">
            <div className="text-center">
              <p className="text-lg">Bir urun secin</p>
              <p className="mt-1 text-sm">Soldaki listeden bir urun secin</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
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

  // ── Queries ─────────────────────────────────────────────────────────────
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

  // ── Mutations ───────────────────────────────────────────────────────────
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
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['suggestions', selectedId] }),
  });

  const rejectMut = useMutation({
    mutationFn: (productId: string) => rejectSuggestion(productId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['suggestions', selectedId] }),
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
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
      {/* ── Top Navbar ──────────────────────────────────────────────── */}
      <header
        className="flex items-center justify-between px-5 py-3"
        style={{
          background: 'var(--color-bg-surface)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
            >
              iS
            </div>
            <span className="text-[15px] font-semibold text-white tracking-tight">
              ikas <span style={{ color: 'var(--color-primary-light)' }}>SEO Agent</span>
            </span>
          </div>

          {/* Divider */}
          <div className="h-5 w-px" style={{ background: 'var(--color-border-light)' }} />

          {/* Actions */}
          <button
            onClick={() => fetchMut.mutate()}
            disabled={fetchMut.isPending}
            className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[13px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {fetchMut.isPending ? 'Cekiliyor...' : 'Urunleri Cek'}
          </button>

          <button
            onClick={() => applyMut.mutate()}
            disabled={applyMut.isPending}
            className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[13px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #10b981, #06b6d4)' }}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            {applyMut.isPending ? 'Uygulaniyor...' : 'Uygula'}
          </button>
        </div>

        <div className="flex items-center gap-3">
          {/* Product count */}
          {productsQ.data && (
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {productsQ.data.total_count} urun
            </span>
          )}

          <a
            href="/settings"
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all"
            style={{
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border-light)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--color-text-primary)';
              e.currentTarget.style.borderColor = 'var(--color-border-light)';
              e.currentTarget.style.background = 'var(--color-bg-hover)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--color-text-secondary)';
              e.currentTarget.style.borderColor = 'var(--color-border-light)';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Ayarlar
          </a>
        </div>
      </header>

      {/* ── Main Content ────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Left Sidebar: Product List ─────────────────────────────── */}
        <aside
          className="flex w-[340px] flex-col"
          style={{
            background: 'var(--color-bg-surface)',
            borderRight: '1px solid var(--color-border)',
          }}
        >
          {/* Filter Tabs */}
          <div
            className="flex gap-1 px-3 py-2.5"
            style={{ borderBottom: '1px solid var(--color-border)' }}
          >
            {(Object.keys(FILTER_LABELS) as FilterTab[]).map((key) => (
              <button
                key={key}
                onClick={() => {
                  setFilter(key);
                  setPage(1);
                }}
                className="rounded-md px-2.5 py-1 text-xs font-medium transition-all"
                style={{
                  background:
                    filter === key ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                  color:
                    filter === key
                      ? 'var(--color-primary-light)'
                      : 'var(--color-text-muted)',
                }}
                onMouseEnter={(e) => {
                  if (filter !== key)
                    e.currentTarget.style.color = 'var(--color-text-secondary)';
                }}
                onMouseLeave={(e) => {
                  if (filter !== key)
                    e.currentTarget.style.color = 'var(--color-text-muted)';
                }}
              >
                {FILTER_LABELS[key]}
              </button>
            ))}
          </div>

          {/* Product List */}
          <div className="flex-1 overflow-auto">
            {productsQ.isLoading ? (
              <div className="space-y-2 p-3">
                {[...Array(8)].map((_, i) => (
                  <div key={i} className="animate-shimmer h-14 rounded-lg" />
                ))}
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
            <div
              className="flex items-center justify-between px-3 py-2"
              style={{
                borderTop: '1px solid var(--color-border)',
                color: 'var(--color-text-muted)',
                fontSize: '12px',
              }}
            >
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded px-2 py-1 transition-all hover:text-white disabled:opacity-30"
              >
                Onceki
              </button>
              <span>
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded px-2 py-1 transition-all hover:text-white disabled:opacity-30"
              >
                Sonraki
              </button>
            </div>
          )}
        </aside>

        {/* ── Center: Detail ──────────────────────────────────────── */}
        <main className="flex flex-1 flex-col overflow-hidden">
          {selectedId && detailQ.data ? (
            <>
              {/* Product header bar */}
              <div
                className="flex items-center justify-between px-6 py-3"
                style={{ borderBottom: '1px solid var(--color-border)' }}
              >
                <div className="flex items-center gap-3">
                  {/* Product image thumbnail */}
                  {(detailQ.data.product.image_url ||
                    detailQ.data.product.image_urls[0]) && (
                    <img
                      src={
                        detailQ.data.product.image_url ||
                        detailQ.data.product.image_urls[0]
                      }
                      alt=""
                      className="h-10 w-10 rounded-lg object-cover"
                      style={{ border: '1px solid var(--color-border-light)' }}
                    />
                  )}
                  <div>
                    <h2 className="text-[15px] font-semibold text-white leading-tight">
                      {detailQ.data.product.name}
                    </h2>
                    <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {detailQ.data.product.category || 'Kategori yok'}
                      {detailQ.data.product.sku && (
                        <>
                          {' '}
                          <span style={{ color: 'var(--color-border-light)' }}>
                            /
                          </span>{' '}
                          {detailQ.data.product.sku}
                        </>
                      )}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => rewriteMut.mutate(selectedId)}
                    disabled={rewriteMut.isPending}
                    className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[13px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
                    style={{ background: 'linear-gradient(135deg, #8b5cf6, #a855f7)' }}
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    {rewriteMut.isPending ? 'Yaziliyor...' : 'Tumunu Yeniden Yaz'}
                  </button>

                  {latestSuggestion?.status === 'pending' && (
                    <>
                      <button
                        onClick={() => approveMut.mutate(selectedId)}
                        className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium text-white transition-all hover:opacity-90"
                        style={{ background: 'linear-gradient(135deg, #10b981, #06b6d4)' }}
                      >
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                        Onayla
                      </button>
                      <button
                        onClick={() => rejectMut.mutate(selectedId)}
                        className="rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all"
                        style={{
                          color: 'var(--color-danger)',
                          border: '1px solid rgba(239, 68, 68, 0.3)',
                          background: 'rgba(239, 68, 68, 0.08)',
                        }}
                      >
                        Reddet
                      </button>
                    </>
                  )}

                  <div className="mx-1 h-5 w-px" style={{ background: 'var(--color-border-light)' }} />

                  <button
                    onClick={() => setShowChat((v) => !v)}
                    className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all"
                    style={{
                      background: showChat
                        ? 'rgba(99, 102, 241, 0.15)'
                        : 'transparent',
                      color: showChat
                        ? 'var(--color-primary-light)'
                        : 'var(--color-text-secondary)',
                      border: `1px solid ${showChat ? 'rgba(99, 102, 241, 0.3)' : 'var(--color-border-light)'}`,
                    }}
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    Chat
                  </button>
                </div>
              </div>

              {/* Body */}
              <div className="flex flex-1 overflow-hidden">
                <div className="flex-1 overflow-y-auto p-6 space-y-5">
                  {detailQ.data.score && (
                    <ScoreCard score={detailQ.data.score} />
                  )}
                  <DiffViewer
                    product={detailQ.data.product}
                    suggestion={latestSuggestion}
                    onRewriteField={handleRewriteField}
                    rewritingField={rewritingField}
                  />
                </div>

                {showChat && (
                  <div
                    className="w-[380px] p-3"
                    style={{ borderLeft: '1px solid var(--color-border)' }}
                  >
                    <ChatPanel productId={selectedId} />
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <div
                  className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl"
                  style={{ background: 'var(--glass-bg)', border: '1px solid var(--color-border)' }}
                >
                  <svg
                    className="h-7 w-7"
                    style={{ color: 'var(--color-text-muted)' }}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                    />
                  </svg>
                </div>
                <p className="text-[15px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                  Bir urun secin
                </p>
                <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  Soldaki listeden bir urun secin
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

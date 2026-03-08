import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import ProductTable from '../components/ProductTable';
import ScoreCard from '../components/ScoreCard';
import ChatPanel from '../components/ChatPanel';
import {
  applyApproved,
  fetchProducts,
  getProduct,
  resetLocalProductData,
  getSettings,
  syncProductsFromIkas,
} from '../api/client';

type FilterTab = 'all' | 'low_score' | 'pending' | 'approved';

const FILTER_LABELS: Record<FilterTab, string> = {
  all: 'Tumu',
  low_score: 'Dusuk Skor',
  pending: 'Bekleyen',
  approved: 'Onaylanan',
};

function normalizeStoreBaseUrl(storeName: string) {
  const normalizedStore = storeName.trim().replace(/^https?:\/\//i, '').replace(/\/+$/, '');
  if (!normalizedStore) {
    return '';
  }
  return normalizedStore.includes('.')
    ? `https://${normalizedStore}`
    : `https://${normalizedStore}.myikas.com`;
}

function slugifyProductName(name?: string | null) {
  const value = (name || '')
    .trim()
    .toLocaleLowerCase('tr-TR')
    .replace(/ı/g, 'i')
    .replace(/ğ/g, 'g')
    .replace(/ü/g, 'u')
    .replace(/ş/g, 's')
    .replace(/ö/g, 'o')
    .replace(/ç/g, 'c')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

  return value;
}

function buildIkasProductUrl(
  storeName: string,
  slug?: string | null,
  productId?: string,
  productName?: string | null,
) {
  const baseUrl = normalizeStoreBaseUrl(storeName);
  if (!baseUrl) {
    return '';
  }

  const normalizedSlug = slug?.trim().replace(/^\/+/, '');
  if (normalizedSlug) {
    return `${baseUrl}/${normalizedSlug}`;
  }

  const guessedSlug = slugifyProductName(productName);
  if (guessedSlug) {
    return `${baseUrl}/${guessedSlug}`;
  }

  const normalizedProductId = productId?.trim();
  if (!normalizedProductId) {
    return '';
  }

  return `${baseUrl}/product/edit/${normalizedProductId}`;
}

export default function Dashboard() {
  const qc = useQueryClient();
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

  const fetchMut = useMutation({
    mutationFn: () => syncProductsFromIkas(),
    onSuccess: (data) => {
      alert(`${data.fetched_count}/${data.total_count} urun ikas'tan senkronlandi.`);
      qc.invalidateQueries({ queryKey: ['products'] });
      qc.invalidateQueries({ queryKey: ['product'] });
    },
  });

  const resetMut = useMutation({
    mutationFn: () => resetLocalProductData(),
    onSuccess: (data) => {
      setSelectedId(null);
      alert(
        `${data.products_deleted} urun, ${data.scores_deleted} skor, ${data.suggestions_deleted} oneri ve ${data.logs_deleted} log silindi.`,
      );
      qc.invalidateQueries({ queryKey: ['products'] });
      qc.invalidateQueries({ queryKey: ['product'] });
      qc.invalidateQueries({ queryKey: ['suggestions'] });
    },
  });

  const applyMut = useMutation({
    mutationFn: () => applyApproved(),
    onSuccess: (data) => {
      alert(`${data.applied}/${data.total} oneri ikas'a uygulandi.`);
      qc.invalidateQueries({ queryKey: ['products'] });
      qc.invalidateQueries({ queryKey: ['suggestions'] });
    },
  });

  const totalPages = productsQ.data
    ? Math.ceil(productsQ.data.total_count / productsQ.data.limit)
    : 1;

  const selectedProduct = detailQ.data?.product;

  const productDetailUrl =
    selectedProduct && settingsQ.data?.store_name
      ? buildIkasProductUrl(
          settingsQ.data.store_name,
          selectedProduct.slug,
          selectedProduct.id,
          selectedProduct.name,
        )
      : '';

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
      <header
        className="flex items-center justify-between px-5 py-3"
        style={{
          background: 'var(--color-bg-surface)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
            >
              iS
            </div>
            <span className="text-[15px] font-semibold tracking-tight text-white">
              ikas <span style={{ color: 'var(--color-primary-light)' }}>SEO Agent</span>
            </span>
          </div>

          <div className="h-5 w-px" style={{ background: 'var(--color-border-light)' }} />

          <button
            onClick={() => fetchMut.mutate()}
            disabled={fetchMut.isPending}
            className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[13px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {fetchMut.isPending ? 'Senkronlaniyor...' : 'Tum Urunleri Cek'}
          </button>

          <button
            onClick={() => {
              if (window.confirm('Local urun cache veritabani sifirlansin mi? Bu islem geri alinamaz.')) {
                resetMut.mutate();
              }
            }}
            disabled={resetMut.isPending}
            className="flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-[13px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #ef4444, #f97316)' }}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 7h12M9 7V4h6v3m-7 4v6m4-6v6m4-6v6M5 7l1 13h12l1-13" />
            </svg>
            {resetMut.isPending ? 'Sifirlaniyor...' : 'DB Sifirla'}
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
          {productsQ.data && (
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {productsQ.data.total_count} urun
            </span>
          )}

          <Link
            to="/settings"
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
          </Link>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside
          className="flex w-[340px] flex-col"
          style={{
            background: 'var(--color-bg-surface)',
            borderRight: '1px solid var(--color-border)',
          }}
        >
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
                  background: filter === key ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
                  color: filter === key ? 'var(--color-primary-light)' : 'var(--color-text-muted)',
                }}
                onMouseEnter={(e) => {
                  if (filter !== key) {
                    e.currentTarget.style.color = 'var(--color-text-secondary)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (filter !== key) {
                    e.currentTarget.style.color = 'var(--color-text-muted)';
                  }
                }}
              >
                {FILTER_LABELS[key]}
              </button>
            ))}
          </div>

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

        <main className="flex flex-1 overflow-hidden">
          {selectedId && detailQ.data ? (
            <>
              <section className="min-w-0 flex flex-1 flex-col overflow-hidden p-6">
                <div className="min-h-0 flex flex-1 flex-col gap-5 overflow-hidden">
                  <div className="min-h-0 flex-1">
                    <ChatPanel
                      productId={selectedId}
                      productName={detailQ.data.product.name}
                      productCategory={detailQ.data.product.category}
                      seoScore={detailQ.data.score?.total_score ?? null}
                      product={detailQ.data.product}
                      score={detailQ.data.score}
                    />
                  </div>
                </div>
              </section>

              <aside
                className="w-[360px] overflow-y-auto"
                style={{
                  borderLeft: '1px solid var(--color-border)',
                  background: 'var(--color-bg-surface)',
                }}
              >
                <div className="space-y-4 p-4">
                  <div
                    className="rounded-2xl px-4 py-3"
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid var(--color-border)',
                    }}
                  >
                    <div
                      className="text-[10px] font-semibold uppercase tracking-[0.18em]"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      SEO Panel
                    </div>
                    <div className="mt-2 text-[13px] font-semibold text-white">
                      {detailQ.data.product.name}
                    </div>
                    <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                      SEO skorunu buradan oku. Rewrite ve diger operasyonlari chat uzerinden yonet.
                    </p>
                    {productDetailUrl ? (
                      <a
                        href={productDetailUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-3 inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[12px] font-medium transition-all hover:opacity-90"
                        style={{
                          background: 'rgba(99, 102, 241, 0.12)',
                          color: '#c7d2fe',
                          border: '1px solid rgba(99, 102, 241, 0.2)',
                        }}
                      >
                        Urun detayina git
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M14 3h7m0 0v7m0-7L10 14" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 5v14h14" />
                        </svg>
                      </a>
                    ) : (
                      <p className="mt-3 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                        Urun detay linki icin magaza adi ayarlarda tanimli olmali.
                      </p>
                    )}
                  </div>

                  {detailQ.data.score ? (
                    <ScoreCard score={detailQ.data.score} />
                  ) : (
                    <div
                      className="rounded-2xl px-4 py-3 text-[12px]"
                      style={{
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid var(--color-border)',
                        color: 'var(--color-text-muted)',
                      }}
                    >
                      Bu urun icin SEO skoru bulunamadi.
                    </div>
                  )}
                </div>
              </aside>
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
                  Soldaki listeden bir urun secin. SEO skoru ve chat paneli acilacak.
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

/**
 * GscPanel — Google Search Console verileri paneli.
 *
 * Site geneli metrikleri (tıklamalar, gösterimler, CTR, pozisyon) gösterir
 * ve seçili ürünün slug'ıyla sayfa URL'lerini eşleştirerek ürün bazlı
 * metrikleri + en iyi sorguları listeler.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getGscStatus, getGscData, syncGsc } from '../../api/client';
import type { GscData, GscPageMetric, GscQueryMetric, Product } from '../../types';

interface Props {
  product?: Product | null;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function aggregatePages(pages: GscPageMetric[]): {
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
} {
  if (!pages.length) return { clicks: 0, impressions: 0, ctr: 0, position: 0 };
  const clicks = pages.reduce((s, p) => s + p.clicks, 0);
  const impressions = pages.reduce((s, p) => s + p.impressions, 0);
  const ctr = impressions ? parseFloat((clicks / impressions * 100).toFixed(2)) : 0;
  const position = impressions
    ? parseFloat((pages.reduce((s, p) => s + p.position * p.impressions, 0) / impressions).toFixed(1))
    : 0;
  return { clicks, impressions, ctr, position };
}

// ── Sub-components ───────────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string | number;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-1 rounded-xl p-3.5"
      style={{
        background: highlight ? 'var(--tint-primary-bg)' : 'var(--color-surface-2)',
        border: `1px solid ${highlight ? 'var(--tint-primary-soft)' : 'var(--color-border)'}`,
      }}
    >
      <div
        className="text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {label}
      </div>
      <div
        className="text-xl font-bold tabular-nums"
        style={{ color: highlight ? 'var(--color-primary-light)' : 'white' }}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function QueryRow({ q }: { q: GscQueryMetric }) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg px-3 py-2"
      style={{ background: 'var(--color-surface-2)' }}
    >
      <div className="min-w-0 flex-1">
        <span className="truncate text-[12px] font-medium text-white">{q.query}</span>
      </div>
      <div className="flex shrink-0 items-center gap-3 text-[11px] tabular-nums" style={{ color: 'var(--color-text-secondary)' }}>
        <span title="Tıklama">{formatNumber(q.clicks)} tık</span>
        <span title="Gösterim" className="hidden sm:inline">{formatNumber(q.impressions)} gör.</span>
        <span title="Ortalama Pozisyon">#{q.position.toFixed(1)}</span>
      </div>
    </div>
  );
}

function NotConnectedPrompt() {
  return (
    <div
      className="flex flex-col items-center gap-3 rounded-2xl p-6 text-center"
      style={{
        background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)',
      }}
    >
      {/* GSC icon */}
      <div
        className="flex h-12 w-12 items-center justify-center rounded-full"
        style={{ background: 'var(--tint-primary-bg)' }}
      >
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} style={{ color: 'var(--color-primary-light)' }}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
        </svg>
      </div>
      <div>
        <div className="text-[13px] font-semibold text-white">Google Search Console bağlı değil</div>
        <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          Tıklama, gösterim ve sıralama verilerini görmek için Settings sayfasından bağlanın.
        </div>
      </div>
      <a
        href="/?page=settings"
        className="mt-1 rounded-lg px-4 py-1.5 text-[12px] font-medium text-white transition-opacity hover:opacity-80"
        style={{ background: 'var(--color-primary)' }}
      >
        Ayarlara Git
      </a>
    </div>
  );
}

// ── Day selector ─────────────────────────────────────────────────────────────

const DAY_OPTIONS = [
  { label: '7 gün', value: 7 },
  { label: '28 gün', value: 28 },
  { label: '90 gün', value: 90 },
];

// ── Main component ────────────────────────────────────────────────────────────

export default function GscPanel({ product }: Props) {
  const [days, setDays] = useState(28);
  const qc = useQueryClient();

  const statusQ = useQuery({
    queryKey: ['gscStatus'],
    queryFn: getGscStatus,
    staleTime: 60_000,
  });

  const dataQ = useQuery({
    queryKey: ['gscData', days],
    queryFn: () => getGscData(days),
    enabled: statusQ.data?.connected === true,
    staleTime: 5 * 60_000,
  });

  const syncMut = useMutation({
    mutationFn: () => syncGsc(days),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gscData'] });
      qc.invalidateQueries({ queryKey: ['gscStatus'] });
    },
  });

  // Loading / error states for status check
  if (statusQ.isLoading) {
    return (
      <div className="flex items-center justify-center p-8" style={{ color: 'var(--color-text-muted)' }}>
        <span className="text-[13px]">Yükleniyor…</span>
      </div>
    );
  }

  if (!statusQ.data?.connected) {
    return <NotConnectedPrompt />;
  }

  const gscData: GscData | undefined = dataQ.data;
  const slug = product?.slug ?? '';

  // Ürün bazlı sayfa eşleştirmesi
  const matchedPages: GscPageMetric[] = slug && gscData
    ? gscData.pages.filter((p) => p.url.includes(slug))
    : [];

  const productMetrics = aggregatePages(matchedPages);

  // Ürün için ilgili sorguları filtrele (herhangi bir eşleşen sayfanın URL'ini içeren sorgular değil,
  // site geneli sorgu listesinden ürün URL'iyle en çok tıklananlar)
  const productQueries: GscQueryMetric[] = gscData
    ? [...gscData.queries]
        .sort((a, b) => b.clicks - a.clicks)
        .slice(0, 10)
    : [];

  const lastSynced = statusQ.data.last_synced
    ? new Date(statusQ.data.last_synced).toLocaleString('tr-TR', {
        day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
      })
    : null;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-semibold text-white">Google Search Console</span>
          {statusQ.data.is_stale && (
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-medium"
              style={{ background: 'var(--tint-warning-bg, rgba(234,179,8,.12))', color: 'var(--color-warning, #ca8a04)' }}
            >
              Eski veri
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Gün seçici */}
          <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--color-border)' }}>
            {DAY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setDays(opt.value)}
                className="px-2.5 py-1 text-[11px] font-medium transition-colors"
                style={{
                  background: days === opt.value ? 'var(--color-primary)' : 'transparent',
                  color: days === opt.value ? 'white' : 'var(--color-text-secondary)',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {/* Sync button */}
          <button
            onClick={() => syncMut.mutate()}
            disabled={syncMut.isPending || dataQ.isLoading}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-50"
            style={{ background: 'var(--color-surface-3)' }}
            title="GSC verilerini yenile"
          >
            <svg
              className={`h-3.5 w-3.5 ${syncMut.isPending ? 'animate-spin' : ''}`}
              viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {syncMut.isPending ? 'Senkronize ediliyor…' : 'Senkronize Et'}
          </button>
        </div>
      </div>

      {/* Son senkronizasyon */}
      {lastSynced && (
        <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          Son senkronizasyon: {lastSynced}
        </div>
      )}

      {dataQ.isLoading && (
        <div className="flex items-center gap-2 py-4" style={{ color: 'var(--color-text-muted)' }}>
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span className="text-[12px]">Veriler yükleniyor…</span>
        </div>
      )}

      {dataQ.isError && (
        <div
          className="rounded-xl p-3 text-[12px]"
          style={{ background: 'rgba(239,68,68,.1)', color: '#f87171' }}
        >
          GSC verisi yüklenemedi. Bağlantıyı ve property URL'ini kontrol edin.
        </div>
      )}

      {gscData && (
        <>
          {/* Site geneli metrikler */}
          <div>
            <div
              className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Site Geneli — Son {days} Gün
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricCard label="Tıklama" value={formatNumber(gscData.totals.clicks)} />
              <MetricCard label="Gösterim" value={formatNumber(gscData.totals.impressions)} />
              <MetricCard label="CTR" value={`${gscData.totals.ctr.toFixed(1)}%`} />
              <MetricCard label="Ort. Pozisyon" value={`#${gscData.totals.position.toFixed(1)}`} />
            </div>
          </div>

          {/* Ürün bazlı metrikler */}
          {product && (
            <div>
              <div
                className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Bu Ürün — {product.name}
              </div>
              {matchedPages.length > 0 ? (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <MetricCard label="Tıklama" value={formatNumber(productMetrics.clicks)} highlight />
                  <MetricCard label="Gösterim" value={formatNumber(productMetrics.impressions)} highlight />
                  <MetricCard label="CTR" value={`${productMetrics.ctr.toFixed(1)}%`} highlight />
                  <MetricCard label="Ort. Pozisyon" value={`#${productMetrics.position.toFixed(1)}`} highlight />
                </div>
              ) : (
                <div
                  className="rounded-xl p-3 text-[12px]"
                  style={{ background: 'var(--color-surface-2)', color: 'var(--color-text-muted)' }}
                >
                  {slug
                    ? `Bu ürünün URL'i (/${slug}) GSC verilerinde bulunamadı. Property URL'inin doğru ayarlandığından emin olun.`
                    : 'Bu ürünün URL bilgisi (slug) mevcut değil.'}
                </div>
              )}
            </div>
          )}

          {/* En iyi arama sorguları */}
          <div>
            <div
              className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              En İyi Arama Sorguları
            </div>
            {productQueries.length > 0 ? (
              <div className="space-y-1.5">
                {productQueries.map((q) => (
                  <QueryRow key={q.query} q={q} />
                ))}
              </div>
            ) : (
              <div className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                Sorgu verisi bulunamadı.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

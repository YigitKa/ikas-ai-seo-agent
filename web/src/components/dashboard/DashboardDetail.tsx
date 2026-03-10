import ChatPanel from '../ChatPanel';
import ScoreCard from '../ScoreCard';
import type { Product, SeoScore } from '../../types';

interface DashboardDetailProps {
  productId: string;
  product: Product;
  score: SeoScore | null;
  productDetailUrl: string;
}

export default function DashboardDetail({
  productId,
  product,
  score,
  productDetailUrl,
}: DashboardDetailProps) {
  return (
    <>
      <section className="min-w-0 flex flex-1 flex-col overflow-hidden p-6">
        <div className="min-h-0 flex flex-1 flex-col gap-5 overflow-hidden">
          <div className="min-h-0 flex-1">
            <ChatPanel
              productId={productId}
              productName={product.name}
              productCategory={product.category}
              seoScore={score?.total_score ?? null}
              product={product}
              score={score}
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
            <div className="mt-2 text-[13px] font-semibold text-white">{product.name}</div>
            <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              SEO skorunu buradan oku. Rewrite ve diger operasyonlari chat uzerinden yonet.
            </p>
            {productDetailUrl ? (
              <a
                href={productDetailUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[12px] font-medium transition-opacity hover:opacity-90"
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

          {score ? (
            <ScoreCard score={score} />
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
  );
}

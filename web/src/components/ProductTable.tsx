import type { ProductWithScore } from '../types';

interface Props {
  items: ProductWithScore[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function scoreBadge(score: number | undefined | null) {
  if (score == null)
    return (
      <span
        className="inline-flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-semibold"
        style={{ color: 'var(--color-text-muted)', background: 'rgba(255,255,255,0.04)' }}
      >
        -
      </span>
    );

  let bg: string;
  let color: string;
  if (score >= 80) {
    bg = 'rgba(16, 185, 129, 0.12)';
    color = '#34d399';
  } else if (score >= 60) {
    bg = 'rgba(245, 158, 11, 0.12)';
    color = '#fbbf24';
  } else if (score >= 40) {
    bg = 'rgba(249, 115, 22, 0.12)';
    color = '#fb923c';
  } else {
    bg = 'rgba(239, 68, 68, 0.12)';
    color = '#f87171';
  }

  return (
    <span
      className="inline-flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold"
      style={{ background: bg, color }}
    >
      {score}
    </span>
  );
}

export default function ProductTable({ items, selectedId, onSelect }: Props) {
  if (items.length === 0) {
    return (
      <div
        className="flex h-40 items-center justify-center px-4 text-center text-[13px]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Urun bulunamadi. ikas'tan urunleri cekmek icin "Urunleri Cek" butonuna basin.
      </div>
    );
  }

  return (
    <div className="py-1">
      {items.map(({ product, score }) => {
        const thumb = product.image_url || product.image_urls[0];
        const isSelected = product.id === selectedId;

        return (
          <button
            key={product.id}
            onClick={() => onSelect(product.id)}
            className={`flex w-full items-center gap-3 px-3 py-2 text-left transition-colors ${
              isSelected ? '' : 'hover:bg-[var(--color-bg-hover)]'
            }`}
            style={{
              background: isSelected ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
              borderLeft: isSelected
                ? '2px solid var(--color-primary)'
                : '2px solid transparent',
            }}
          >
            {thumb ? (
              <img
                src={thumb}
                alt=""
                className="h-9 w-9 flex-shrink-0 rounded-lg object-cover"
                style={{ border: '1px solid var(--color-border)' }}
                loading="lazy"
              />
            ) : (
              <div
                className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg"
                style={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)' }}
              >
                <svg
                  className="h-4 w-4"
                  style={{ color: 'var(--color-text-muted)' }}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            )}

            <div className="min-w-0 flex-1">
              <p
                className="truncate text-[13px] font-medium leading-tight"
                style={{ color: isSelected ? 'white' : 'var(--color-text-primary)' }}
              >
                {product.name}
              </p>
              {product.category && (
                <p className="mt-0.5 truncate text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                  {product.category}
                </p>
              )}
            </div>

            {scoreBadge(score?.total_score)}
          </button>
        );
      })}
    </div>
  );
}

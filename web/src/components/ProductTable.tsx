import type { ProductWithScore } from '../types';

interface Props {
  items: ProductWithScore[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function scoreBadge(score: number | undefined | null) {
  if (score == null) return <span className="text-xs text-gray-500">-</span>;
  let color = 'bg-red-500/20 text-red-400';
  if (score >= 80) color = 'bg-green-500/20 text-green-400';
  else if (score >= 60) color = 'bg-yellow-500/20 text-yellow-400';
  else if (score >= 40) color = 'bg-orange-500/20 text-orange-400';
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}>
      {score}
    </span>
  );
}

export default function ProductTable({ items, selectedId, onSelect }: Props) {
  if (items.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-gray-500">
        Urun bulunamadi. ikas'tan urunleri cekmek icin "Urunleri Cek" butonuna basin.
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-700 text-xs uppercase text-gray-500">
            <th className="px-3 py-2 w-12"></th>
            <th className="px-3 py-2">Urun Adi</th>
            <th className="px-3 py-2 w-20 text-center">Skor</th>
            <th className="px-3 py-2 w-24 text-right">Fiyat</th>
          </tr>
        </thead>
        <tbody>
          {items.map(({ product, score }) => {
            const thumb = product.image_url || product.image_urls[0];
            const isSelected = product.id === selectedId;
            return (
              <tr
                key={product.id}
                onClick={() => onSelect(product.id)}
                className={`cursor-pointer border-b border-gray-700/50 transition hover:bg-gray-700/40 ${
                  isSelected ? 'bg-blue-500/10' : ''
                }`}
              >
                <td className="px-3 py-2">
                  {thumb ? (
                    <img
                      src={thumb}
                      alt=""
                      className="h-8 w-8 rounded object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="h-8 w-8 rounded bg-gray-700" />
                  )}
                </td>
                <td className="px-3 py-2 font-medium text-gray-200 truncate max-w-[300px]">
                  {product.name}
                </td>
                <td className="px-3 py-2 text-center">
                  {scoreBadge(score?.total_score)}
                </td>
                <td className="px-3 py-2 text-right text-gray-400">
                  {product.price != null ? `${product.price.toFixed(2)} TL` : '-'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

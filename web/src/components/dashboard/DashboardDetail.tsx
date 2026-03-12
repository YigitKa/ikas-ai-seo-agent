import ChatPanel from '../ChatPanel';
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
            productDetailUrl={productDetailUrl}
          />
        </div>
      </div>
    </section>
  );
}

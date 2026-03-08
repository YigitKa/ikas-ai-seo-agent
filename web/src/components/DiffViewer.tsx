interface DiffFieldProps {
  label: string;
  original: string;
  suggested: string;
  isHtml?: boolean;
  onRewrite?: () => void;
  isRewriting?: boolean;
}

function DiffField({ label, original, suggested, isHtml, onRewrite, isRewriting }: DiffFieldProps) {
  const hasChange = suggested && suggested !== original;

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400">{label}</h4>
        {onRewrite && (
          <button
            onClick={onRewrite}
            disabled={isRewriting}
            className="rounded bg-blue-600 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {isRewriting ? 'Yaziliyor...' : 'AI Yeniden Yaz'}
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase text-gray-500">Orijinal</div>
          <div className="rounded border border-gray-700 bg-gray-900/50 p-3 text-sm text-gray-300">
            {isHtml ? (
              <div dangerouslySetInnerHTML={{ __html: original || '<em class="text-gray-600">Bos</em>' }} />
            ) : (
              <span>{original || <em className="text-gray-600">Bos</em>}</span>
            )}
          </div>
        </div>
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase text-gray-500">
            {hasChange ? 'Onerilen' : 'Onerilen (henuz yok)'}
          </div>
          <div
            className={`rounded border p-3 text-sm ${
              hasChange
                ? 'border-green-700/50 bg-green-900/10 text-green-200'
                : 'border-gray-700 bg-gray-900/50 text-gray-500'
            }`}
          >
            {isHtml && suggested ? (
              <div dangerouslySetInnerHTML={{ __html: suggested }} />
            ) : (
              <span>{suggested || '-'}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

import type { Product, SeoSuggestion } from '../types';

interface Props {
  product: Product;
  suggestion: SeoSuggestion | null;
  onRewriteField?: (field: string) => void;
  rewritingField?: string | null;
}

export default function DiffViewer({ product, suggestion, onRewriteField, rewritingField }: Props) {
  return (
    <div className="space-y-3">
      <DiffField
        label="Urun Adi"
        original={product.name}
        suggested={suggestion?.suggested_name || ''}
        onRewrite={() => onRewriteField?.('name')}
        isRewriting={rewritingField === 'name'}
      />
      <DiffField
        label="Aciklama (TR)"
        original={product.description_translations.tr || product.description}
        suggested={suggestion?.suggested_description || ''}
        isHtml
        onRewrite={() => onRewriteField?.('desc_tr')}
        isRewriting={rewritingField === 'desc_tr'}
      />
      <DiffField
        label="Aciklama (EN)"
        original={product.description_translations.en || ''}
        suggested={suggestion?.suggested_description_en || ''}
        isHtml
        onRewrite={() => onRewriteField?.('desc_en')}
        isRewriting={rewritingField === 'desc_en'}
      />
      <DiffField
        label="Meta Title"
        original={product.meta_title || ''}
        suggested={suggestion?.suggested_meta_title || ''}
        onRewrite={() => onRewriteField?.('meta_title')}
        isRewriting={rewritingField === 'meta_title'}
      />
      <DiffField
        label="Meta Description"
        original={product.meta_description || ''}
        suggested={suggestion?.suggested_meta_description || ''}
        onRewrite={() => onRewriteField?.('meta_desc')}
        isRewriting={rewritingField === 'meta_desc'}
      />
    </div>
  );
}

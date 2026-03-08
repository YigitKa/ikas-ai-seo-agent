import { useState } from 'react';
import type { Product, SeoSuggestion } from '../types';

interface DiffFieldProps {
  label: string;
  original: string;
  suggested: string;
  isHtml?: boolean;
  onRewrite?: () => void;
  isRewriting?: boolean;
}

function DiffField({
  label,
  original,
  suggested,
  isHtml,
  onRewrite,
  isRewriting,
}: DiffFieldProps) {
  const hasChange = suggested && suggested !== original;
  const [activeTab, setActiveTab] = useState<'original' | 'suggested'>('original');

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: 'var(--glass-bg)',
        border: '1px solid var(--color-border)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center gap-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-secondary)' }}>
            {label}
          </h4>
          {hasChange && (
            <span
              className="rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase"
              style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#34d399' }}
            >
              Degisiklik var
            </span>
          )}
        </div>
        {onRewrite && (
          <button
            onClick={onRewrite}
            disabled={isRewriting}
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-medium text-white transition-all hover:opacity-90 disabled:opacity-40"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            {isRewriting ? (
              <>
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Yaziliyor...
              </>
            ) : (
              <>
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                AI Yeniden Yaz
              </>
            )}
          </button>
        )}
      </div>

      {/* Tab Switcher - Mobile friendly */}
      <div
        className="flex gap-1 px-4 py-2"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <button
          onClick={() => setActiveTab('original')}
          className="rounded-md px-2.5 py-1 text-[11px] font-medium transition-all"
          style={{
            background: activeTab === 'original' ? 'rgba(255,255,255,0.06)' : 'transparent',
            color: activeTab === 'original' ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
          }}
        >
          Orijinal
        </button>
        <button
          onClick={() => setActiveTab('suggested')}
          className="rounded-md px-2.5 py-1 text-[11px] font-medium transition-all"
          style={{
            background: activeTab === 'suggested'
              ? hasChange
                ? 'rgba(16, 185, 129, 0.1)'
                : 'rgba(255,255,255,0.06)'
              : 'transparent',
            color: activeTab === 'suggested'
              ? hasChange
                ? '#34d399'
                : 'var(--color-text-primary)'
              : 'var(--color-text-muted)',
          }}
        >
          Onerilen {!hasChange && '(henuz yok)'}
        </button>
      </div>

      {/* Content area - also show side-by-side on wide screens */}
      <div className="hidden lg:grid lg:grid-cols-2">
        {/* Original */}
        <div className="p-4" style={{ borderRight: '1px solid var(--color-border)' }}>
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            Orijinal
          </div>
          <div className="text-[13px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
            {isHtml ? (
              <div
                className="html-content"
                dangerouslySetInnerHTML={{
                  __html: original || '<em style="color: var(--color-text-muted)">Bos</em>',
                }}
              />
            ) : (
              <span>{original || <em style={{ color: 'var(--color-text-muted)' }}>Bos</em>}</span>
            )}
          </div>
        </div>

        {/* Suggested */}
        <div
          className="p-4"
          style={{
            background: hasChange ? 'rgba(16, 185, 129, 0.03)' : 'transparent',
          }}
        >
          <div
            className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: hasChange ? '#34d399' : 'var(--color-text-muted)' }}
          >
            Onerilen
          </div>
          <div
            className="text-[13px] leading-relaxed"
            style={{ color: hasChange ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}
          >
            {isHtml && suggested ? (
              <div className="html-content" dangerouslySetInnerHTML={{ __html: suggested }} />
            ) : (
              <span>{suggested || '-'}</span>
            )}
          </div>
        </div>
      </div>

      {/* Mobile: Tab content */}
      <div className="lg:hidden p-4">
        {activeTab === 'original' ? (
          <div className="text-[13px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
            {isHtml ? (
              <div
                className="html-content"
                dangerouslySetInnerHTML={{
                  __html: original || '<em style="color: var(--color-text-muted)">Bos</em>',
                }}
              />
            ) : (
              <span>{original || <em style={{ color: 'var(--color-text-muted)' }}>Bos</em>}</span>
            )}
          </div>
        ) : (
          <div
            className="text-[13px] leading-relaxed"
            style={{ color: hasChange ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}
          >
            {isHtml && suggested ? (
              <div className="html-content" dangerouslySetInnerHTML={{ __html: suggested }} />
            ) : (
              <span>{suggested || '-'}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface Props {
  product: Product;
  suggestion: SeoSuggestion | null;
  onRewriteField?: (field: string) => void;
  rewritingField?: string | null;
}

export default function DiffViewer({
  product,
  suggestion,
  onRewriteField,
  rewritingField,
}: Props) {
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

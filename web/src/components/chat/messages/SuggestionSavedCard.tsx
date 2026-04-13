import { useState } from 'react';
import type { SuggestionSavedInfo } from '../../../types';
import Modal from '../../../shared/ui/Modal';

export default function SuggestionSavedCard({ info }: { info: SuggestionSavedInfo }) {
  const [previewField, setPreviewField] = useState<{ label: string; html: string } | null>(null);

  const fieldLabels: Record<string, string> = {
    suggested_name: 'Urun Adi',
    suggested_meta_title: 'Meta Title',
    suggested_meta_description: 'Meta Description',
    suggested_description: 'Aciklama (TR)',
    suggested_description_en: 'Aciklama (EN)',
  };

  const htmlFields = new Set(['suggested_description', 'suggested_description_en']);

  const entries = Object.entries(info.fields).filter(([, v]) => v.trim());

  return (
    <>
      <div
        className="rounded-lg px-3 py-2.5 text-xs"
        style={{ background: 'var(--tint-success-bg)', border: '1px solid var(--color-border-success)' }}
      >
        <div
          className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-[0.16em]"
          style={{ color: 'rgba(34, 197, 94, 0.8)' }}
        >
          Oneri Kaydedildi
        </div>
        <div className="space-y-1">
          {entries.map(([key, value]) => (
            <div key={key} className="flex items-start gap-2">
              <span
                className="flex-shrink-0 font-medium"
                style={{ color: 'rgba(34, 197, 94, 0.7)', minWidth: '90px' }}
              >
                {fieldLabels[key] || key}:
              </span>
              <span className="flex-1" style={{ color: 'rgba(34, 197, 94, 0.9)' }}>
                {value.length > 80 ? value.slice(0, 80) + '...' : value}
              </span>
              {value.length > 80 && (
                <button
                  type="button"
                  onClick={() => setPreviewField({ label: fieldLabels[key] || key, html: value })}
                  className="flex-shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors hover:brightness-125"
                  style={{
                    color: 'rgba(34, 197, 94, 0.9)',
                    background: 'var(--tint-success-soft)',
                    border: '1px solid var(--color-border-success)',
                  }}
                >
                  On Izle
                </button>
              )}
            </div>
          ))}
        </div>
        <div className="mt-2 text-[11px]" style={{ color: 'rgba(34, 197, 94, 0.5)' }}>
          Chatte onaylayip secili urune ikas uzerinde uygulayabilirsiniz.
        </div>
      </div>

      {previewField && (
        <Modal
          open
          onClose={() => setPreviewField(null)}
          title={previewField.label}
          subtitle="Onerilen icerik on izlemesi"
          maxWidth="max-w-3xl"
        >
          {htmlFields.has(
            Object.keys(info.fields).find((k) => (fieldLabels[k] || k) === previewField.label) || '',
          ) ? (
            <div
              className="prose prose-invert max-w-none text-sm"
              style={{ color: 'var(--color-text-primary)' }}
              dangerouslySetInnerHTML={{ __html: previewField.html }}
            />
          ) : (
            <p className="whitespace-pre-wrap text-sm" style={{ color: 'var(--color-text-primary)' }}>
              {previewField.html}
            </p>
          )}
        </Modal>
      )}
    </>
  );
}

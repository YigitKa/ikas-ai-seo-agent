import type { SuggestionSavedInfo } from '../../../types';

export default function SuggestionSavedCard({ info }: { info: SuggestionSavedInfo }) {
  const fieldLabels: Record<string, string> = {
    suggested_name: 'Urun Adi',
    suggested_meta_title: 'Meta Title',
    suggested_meta_description: 'Meta Description',
    suggested_description: 'Aciklama (TR)',
    suggested_description_en: 'Aciklama (EN)',
  };

  const entries = Object.entries(info.fields).filter(([, v]) => v.trim());

  return (
    <div
      className="rounded-lg px-3 py-2.5 text-xs"
      style={{ background: 'rgba(34, 197, 94, 0.08)', border: '1px solid rgba(34, 197, 94, 0.2)' }}
    >
      <div
        className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'rgba(34, 197, 94, 0.8)' }}
      >
        Oneri Kaydedildi
      </div>
      <div className="space-y-1">
        {entries.map(([key, value]) => (
          <div key={key} className="flex gap-2">
            <span
              className="flex-shrink-0 font-medium"
              style={{ color: 'rgba(34, 197, 94, 0.7)', minWidth: '90px' }}
            >
              {fieldLabels[key] || key}:
            </span>
            <span style={{ color: 'rgba(34, 197, 94, 0.9)' }}>
              {value.length > 80 ? value.slice(0, 80) + '...' : value}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-2 text-[11px]" style={{ color: 'rgba(34, 197, 94, 0.5)' }}>
        Chatte onaylayip secili urune ikas uzerinde uygulayabilirsiniz.
      </div>
    </div>
  );
}

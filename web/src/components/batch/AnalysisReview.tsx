import { useEffect, useRef, useState } from 'react';
import type { BatchItem, BatchJob } from '../../types';

type BatchDecision = 'approved' | 'rejected' | 'revised';

interface Props {
  job: BatchJob;
  items: BatchItem[];
  onDecision: (itemId: number, decision: BatchDecision, revisedData?: Record<string, string>) => void;
  onRegenerate: (itemId: number) => void;
  onFieldRegenerate: (itemId: number, fieldKey: string) => void;
  onBulkDecision?: (itemIds: number[], decision: 'approved' | 'rejected') => void;
  onApplyAll: () => void;
  onStop?: () => void;
  onBack?: () => void;
  isMutating: boolean;
  regeneratingKey?: string | null;
}

interface DiffField {
  key: string;
  label: string;
  richText?: boolean;
  multiline?: boolean;
}

type DraftMap = Record<number, Record<string, string>>;

const DIFF_FIELDS: DiffField[] = [
  { key: 'name', label: 'Başlık' },
  { key: 'meta_title', label: 'Meta Başlık' },
  { key: 'meta_description', label: 'Meta Açıklama', multiline: true },
  { key: 'description', label: 'Açıklama', richText: true, multiline: true },
  { key: 'description_en', label: 'Açıklama (EN)', richText: true, multiline: true },
];

const ALLOWED_HTML_TAGS = new Set(['p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'u', 'span', 'div', 'h2', 'h3', 'h4']);

function hasHtmlMarkup(value: string): boolean {
  return /<[^>]+>/.test(value);
}

function getDisplayFields(item: BatchItem, targetFields: string[]): DiffField[] {
  const rawActiveFields = item.suggestion_data?.active_fields;
  const activeFields = Array.isArray(rawActiveFields) ? rawActiveFields.map((field) => String(field)) : targetFields;
  const allowedFields = new Set(activeFields.length ? activeFields : targetFields);
  return DIFF_FIELDS.filter((field) => allowedFields.has(field.key));
}

function getSuggestedValue(item: BatchItem, fieldKey: string): string {
  return String(item.suggestion_data?.[`suggested_${fieldKey}`] ?? '');
}

function getOriginalValue(item: BatchItem, fieldKey: string): string {
  return String(item.suggestion_data?.[`original_${fieldKey}`] ?? '');
}

function getFieldError(item: BatchItem, fieldKey: string): string {
  const fieldErrors = item.suggestion_data?.field_errors;
  if (!fieldErrors || typeof fieldErrors !== 'object') return '';
  return String((fieldErrors as Record<string, unknown>)[fieldKey] ?? '');
}

function hasActionableSuggestion(item: BatchItem, targetFields: string[]): boolean {
  return getDisplayFields(item, targetFields).some((field) => getSuggestedValue(item, field.key).trim() !== '');
}

function sanitizeHtmlPreview(value: string): string {
  const doc = new DOMParser().parseFromString(value, 'text/html');
  doc.querySelectorAll('script, style').forEach((node) => node.remove());
  Array.from(doc.body.querySelectorAll('*')).forEach((element) => {
    const tagName = element.tagName.toLowerCase();
    if (!ALLOWED_HTML_TAGS.has(tagName)) {
      element.replaceWith(...Array.from(element.childNodes));
      return;
    }
    Array.from(element.attributes).forEach((attribute) => {
      if (
        attribute.name.startsWith('on')
        || attribute.name === 'style'
        || attribute.name === 'class'
        || attribute.name === 'color'
        || attribute.name === 'size'
        || attribute.name === 'face'
      ) {
        element.removeAttribute(attribute.name);
      }
    });
  });
  return doc.body.innerHTML;
}

function HtmlPreview({
  value,
  emphasized = false,
}: {
  value: string;
  emphasized?: boolean;
}) {
  if (!value.trim()) {
    return <span style={{ opacity: 0.45 }}>Henüz üretilmedi</span>;
  }

  if (hasHtmlMarkup(value)) {
    return (
      <div
        className="html-content"
        style={{ color: emphasized ? '#22c55e' : 'var(--color-text-secondary)' }}
        dangerouslySetInnerHTML={{ __html: sanitizeHtmlPreview(value) }}
      />
    );
  }

  return (
    <p
      className="text-[12px] leading-relaxed whitespace-pre-wrap"
      style={{ color: emphasized ? '#22c55e' : 'var(--color-text-secondary)' }}
    >
      {value}
    </p>
  );
}

function ToolbarButton({
  children,
  onClick,
}: {
  children: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md px-2 py-1 text-[11px] font-semibold transition hover:opacity-80"
      style={{
        background: 'rgba(99,102,241,0.08)',
        border: '1px solid rgba(99,102,241,0.18)',
        color: '#c7d2fe',
      }}
    >
      {children}
    </button>
  );
}

function HtmlEditor({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (next: string) => void;
  disabled: boolean;
}) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const wrapSelection = (prefix: string, suffix = prefix) => {
    const textarea = textareaRef.current;
    if (!textarea || disabled) return;
    const { selectionStart, selectionEnd } = textarea;
    const selected = textarea.value.slice(selectionStart, selectionEnd) || 'Metin';
    const nextValue = `${textarea.value.slice(0, selectionStart)}${prefix}${selected}${suffix}${textarea.value.slice(selectionEnd)}`;
    onChange(nextValue);
    queueMicrotask(() => {
      const caretStart = selectionStart + prefix.length;
      const caretEnd = caretStart + selected.length;
      textarea.focus();
      textarea.setSelectionRange(caretStart, caretEnd);
    });
  };

  const insertList = () => wrapSelection('<ul>\n  <li>', '</li>\n</ul>');
  const insertBreak = () => wrapSelection('<br />', '');

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <ToolbarButton onClick={() => wrapSelection('<h2>', '</h2>')}>H2</ToolbarButton>
        <ToolbarButton onClick={() => wrapSelection('<p>', '</p>')}>P</ToolbarButton>
        <ToolbarButton onClick={() => wrapSelection('<strong>', '</strong>')}>Kalın</ToolbarButton>
        <ToolbarButton onClick={insertList}>Liste</ToolbarButton>
        <ToolbarButton onClick={insertBreak}>Satır</ToolbarButton>
      </div>

      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={10}
        disabled={disabled}
        className="w-full resize-y rounded-lg px-3 py-2 font-mono text-[12px] leading-relaxed outline-none"
        style={{
          background: 'rgba(34,197,94,0.05)',
          border: '1px solid rgba(34,197,94,0.2)',
          color: 'var(--color-text-primary)',
          minHeight: 220,
        }}
      />
    </div>
  );
}

function PlainEditor({
  value,
  onChange,
  multiline = false,
  disabled,
}: {
  value: string;
  onChange: (next: string) => void;
  multiline?: boolean;
  disabled: boolean;
}) {
  if (multiline) {
    return (
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        disabled={disabled}
        className="w-full resize-y rounded-lg px-3 py-2 text-[12px] leading-relaxed outline-none"
        style={{
          background: 'rgba(34,197,94,0.05)',
          border: '1px solid rgba(34,197,94,0.2)',
          color: 'var(--color-text-primary)',
          minHeight: 112,
        }}
      />
    );
  }

  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      className="w-full rounded-lg px-3 py-2 text-[12px] leading-relaxed outline-none"
      style={{
        background: 'rgba(34,197,94,0.05)',
        border: '1px solid rgba(34,197,94,0.2)',
        color: 'var(--color-text-primary)',
      }}
    />
  );
}

function DiffRow({
  field,
  original,
  draftValue,
  fieldError,
  isDirty,
  isRegenerating,
  disabled,
  onChange,
  onRegenerate,
}: {
  field: DiffField;
  original: string;
  draftValue: string;
  fieldError: string;
  isDirty: boolean;
  isRegenerating: boolean;
  disabled: boolean;
  onChange: (next: string) => void;
  onRegenerate: () => void;
}) {
  const previewAccent = draftValue.trim() !== '' && original !== draftValue;
  const showHtmlWarning = Boolean(field.richText && draftValue.trim() !== '' && !hasHtmlMarkup(draftValue));

  return (
    <div
      className="rounded-xl border px-3 py-3"
      style={{ background: 'var(--color-bg-primary)', borderColor: 'var(--color-border)' }}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            {field.label}
          </span>
          {isDirty && (
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
              style={{ background: 'rgba(245,158,11,0.12)', color: '#f59e0b' }}
            >
              Düzenlendi
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={disabled || isRegenerating}
          className="rounded-lg px-3 py-1.5 text-[11px] font-medium transition hover:opacity-80 disabled:opacity-50"
          style={{
            background: 'rgba(99,102,241,0.1)',
            border: '1px solid rgba(99,102,241,0.24)',
            color: '#818cf8',
          }}
        >
          {isRegenerating ? 'Üretiliyor...' : 'Yeniden Üret'}
        </button>
      </div>

      {field.richText ? (
        <div className="space-y-3">
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Mevcut Formatlı Görünüm
            </p>
            <div
              className="rounded-lg px-3 py-3 text-[12px] leading-relaxed"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-secondary)',
                minHeight: 140,
                maxHeight: 280,
                overflowY: 'auto',
              }}
            >
              <HtmlPreview value={original} />
            </div>
            {hasHtmlMarkup(original) && (
              <details className="mt-2">
                <summary className="cursor-pointer text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                  {"Ham HTML'yi göster"}
                </summary>
                <pre
                  className="mt-2 overflow-x-auto rounded-lg px-3 py-2 text-[11px]"
                  style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}
                >
                  {original}
                </pre>
              </details>
            )}
          </div>

          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Önerilen HTML Kodu
            </p>
            <HtmlEditor value={draftValue} onChange={onChange} disabled={disabled} />
            {showHtmlWarning && (
              <p className="mt-2 text-[11px]" style={{ color: '#f59e0b' }}>
                Bu içerikte HTML etiketi yok. Onaylamadan önce başlık, paragraf veya liste ekleyebilirsiniz.
              </p>
            )}
          </div>

          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Formatlı Önizleme
            </p>
            <div
              className="rounded-lg px-3 py-3 text-[12px] leading-relaxed"
              style={{
                background: previewAccent ? 'rgba(34,197,94,0.08)' : 'rgba(255,255,255,0.03)',
                border: previewAccent ? '1px solid rgba(34,197,94,0.22)' : '1px solid var(--color-border)',
                color: previewAccent ? '#22c55e' : 'var(--color-text-secondary)',
                minHeight: 160,
                maxHeight: 320,
                overflowY: 'auto',
              }}
            >
              <HtmlPreview value={draftValue} emphasized={previewAccent} />
            </div>
          </div>
        </div>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Mevcut
            </p>
            <div
              className="rounded-lg px-3 py-2 text-[12px] leading-relaxed whitespace-pre-wrap"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-secondary)',
                minHeight: field.multiline ? 112 : 42,
              }}
            >
              {original || <span style={{ opacity: 0.45 }}>Boş</span>}
            </div>
          </div>

          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
              Önerilen
            </p>
            <PlainEditor value={draftValue} onChange={onChange} multiline={field.multiline} disabled={disabled} />
          </div>
        </div>
      )}

      {fieldError && (
        <p className="mt-3 text-[11px]" style={{ color: '#f59e0b' }}>
          {fieldError}
        </p>
      )}
    </div>
  );
}

function ScoreBadge({ before, after }: { before: number | null; after: number | null }) {
  if (before == null || after == null) return null;
  const delta = after - before;
  const color = delta > 0 ? '#22c55e' : delta < 0 ? '#ef4444' : '#94a3b8';
  return (
    <span
      className="rounded-full px-2 py-0.5 text-[11px] font-bold"
      style={{ background: `${color}18`, color }}
    >
      {before} → {after} ({delta > 0 ? '+' : ''}{delta})
    </span>
  );
}

function ItemCard({
  item,
  analysisComplete,
  targetFields,
  regeneratingKey,
  getDraftValue,
  getItemRevisedData,
  onDraftChange,
  onDecision,
  onRegenerate,
  onFieldRegenerate,
}: {
  item: BatchItem;
  analysisComplete: boolean;
  targetFields: string[];
  regeneratingKey: string | null;
  getDraftValue: (fieldKey: string) => string;
  getItemRevisedData: () => Record<string, string> | undefined;
  onDraftChange: (fieldKey: string, next: string) => void;
  onDecision: (decision: BatchDecision, revisedData?: Record<string, string>) => void;
  onRegenerate: () => void;
  onFieldRegenerate: (fieldKey: string) => void;
}) {
  const displayFields = getDisplayFields(item, targetFields);
  const hasSuggestion = displayFields.some((field) => getDraftValue(field.key).trim() !== '');
  const isItemRegenerating = regeneratingKey === `item:${item.id}`;
  const isProcessing = isItemRegenerating || (item.status === 'pending' && !analysisComplete);
  const noSuggestion = !hasSuggestion && analysisComplete && item.status !== 'failed' && item.status !== 'skipped';
  const canRegenerateWholeItem = analysisComplete && displayFields.length === 0;
  const revisedData = getItemRevisedData();
  const hasEdits = !!revisedData && Object.keys(revisedData).length > 0;
  const approveDecision: BatchDecision = hasEdits ? 'revised' : 'approved';

  return (
    <div
      className="rounded-xl p-4"
      style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <p className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {item.product_name}
          </p>
          <ScoreBadge before={item.score_before} after={item.score_after} />
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {item.status === 'approved' && !hasEdits && (
            <button
              type="button"
              onClick={() => onDecision('rejected')}
              disabled={isProcessing}
              className="rounded-full px-2 py-0.5 text-[11px] font-medium transition hover:opacity-70 disabled:opacity-50"
              style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e' }}
              title="Kararı değiştir"
            >
              ✓ Onaylandı
            </button>
          )}

          {item.status === 'rejected' && !hasEdits && (
            <button
              type="button"
              onClick={() => onDecision('approved')}
              disabled={isProcessing}
              className="rounded-full px-2 py-0.5 text-[11px] font-medium transition hover:opacity-70 disabled:opacity-50"
              style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}
              title="Kararı değiştir"
            >
              ✕ Reddedildi
            </button>
          )}

          {(item.status === 'analyzed' || item.status === 'pending' || hasEdits || item.status === 'rejected') && hasSuggestion && (
            <>
              <button
                type="button"
                onClick={() => onDecision(approveDecision, revisedData)}
                disabled={isProcessing}
                className="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white transition hover:opacity-80 disabled:opacity-50"
                style={{ background: '#22c55e' }}
              >
                {hasEdits ? 'Düzenleyip Onayla' : 'Onayla'}
              </button>
              <button
                type="button"
                onClick={() => onDecision('rejected')}
                disabled={isProcessing}
                className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition hover:opacity-80 disabled:opacity-50"
                style={{
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.3)',
                  color: '#ef4444',
                }}
              >
                Reddet
              </button>
            </>
          )}

          {canRegenerateWholeItem && (
            <button
              type="button"
              onClick={onRegenerate}
              disabled={isProcessing}
              className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition hover:opacity-80 disabled:opacity-50"
              style={{
                background: 'rgba(99,102,241,0.1)',
                border: '1px solid rgba(99,102,241,0.24)',
                color: '#818cf8',
              }}
            >
              {isItemRegenerating ? 'Yeniden Üretiliyor...' : 'Tüm Alanları Yeniden Üret'}
            </button>
          )}
        </div>
      </div>

      {isProcessing && (
        <div className="mb-4 flex items-center gap-2 py-2">
          <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="#6366f1" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            AI alanları yeniden üretiyor...
          </span>
        </div>
      )}

      {noSuggestion && (
        <p className="mb-4 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
          Seçili alanlar için henüz öneri yok. Her alan için ayrı yeniden üret kullanabilirsiniz.
        </p>
      )}

      {item.status === 'failed' && (
        <p className="mb-4 text-[12px]" style={{ color: '#ef4444' }}>
          Hata: {item.skip_reason || 'Bilinmeyen hata'}
        </p>
      )}

      {item.status === 'skipped' && (
        <p className="mb-4 text-[12px]" style={{ color: '#f59e0b' }}>
          Atlandı: {item.skip_reason || 'AI bu ürün için öneri oluşturamadı.'}
        </p>
      )}

      {displayFields.length > 0 && (
        <div className="space-y-3">
          {displayFields.map((field) => {
            const original = getOriginalValue(item, field.key);
            const draftValue = getDraftValue(field.key);
            return (
              <DiffRow
                key={field.key}
                field={field}
                original={original}
                draftValue={draftValue}
                fieldError={getFieldError(item, field.key)}
                isDirty={draftValue !== getSuggestedValue(item, field.key)}
                isRegenerating={regeneratingKey === `${item.id}:${field.key}`}
                disabled={isProcessing}
                onChange={(next) => onDraftChange(field.key, next)}
                onRegenerate={() => onFieldRegenerate(field.key)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function AnalysisReview({
  job,
  items,
  onDecision,
  onRegenerate,
  onFieldRegenerate,
  onBulkDecision,
  onApplyAll,
  onStop,
  onBack,
  isMutating,
  regeneratingKey = null,
}: Props) {
  const analysisComplete = job.status === 'analyzed';
  const targetFields = job.config.target_fields ?? DIFF_FIELDS.map((field) => field.key);
  const visibleItems = items.filter((item) => item.status !== 'applied' && item.status !== 'rolled_back');
  const [drafts, setDrafts] = useState<DraftMap>({});
  const serverValuesRef = useRef<Record<string, string>>({});

  useEffect(() => {
    setDrafts((previous) => {
      let changed = false;
      const next: DraftMap = { ...previous };

      visibleItems.forEach((item) => {
        const fields = getDisplayFields(item, targetFields);
        if (fields.length === 0) return;

        const itemDrafts = { ...(next[item.id] ?? {}) };
        let itemChanged = false;

        fields.forEach((field) => {
          const refKey = `${item.id}:${field.key}`;
          const serverValue = getSuggestedValue(item, field.key);
          const previousServerValue = serverValuesRef.current[refKey];
          if (itemDrafts[field.key] === undefined || itemDrafts[field.key] === previousServerValue) {
            itemDrafts[field.key] = serverValue;
            itemChanged = true;
          }
          serverValuesRef.current[refKey] = serverValue;
        });

        if (itemChanged) {
          next[item.id] = itemDrafts;
          changed = true;
        }
      });

      return changed ? next : previous;
    });
  }, [visibleItems, targetFields]);

  const getDraftValue = (item: BatchItem, fieldKey: string): string => {
    return drafts[item.id]?.[fieldKey] ?? getSuggestedValue(item, fieldKey);
  };

  const setDraftValue = (itemId: number, fieldKey: string, value: string) => {
    setDrafts((previous) => ({
      ...previous,
      [itemId]: {
        ...(previous[itemId] ?? {}),
        [fieldKey]: value,
      },
    }));
  };

  const resetDraftsForItem = (item: BatchItem) => {
    const fields = getDisplayFields(item, targetFields);
    setDrafts((previous) => {
      const itemDrafts = { ...(previous[item.id] ?? {}) };
      fields.forEach((field) => {
        itemDrafts[field.key] = getSuggestedValue(item, field.key);
      });
      return {
        ...previous,
        [item.id]: itemDrafts,
      };
    });
  };

  const getItemRevisedData = (item: BatchItem): Record<string, string> | undefined => {
    const revisedData: Record<string, string> = {};
    getDisplayFields(item, targetFields).forEach((field) => {
      const draftValue = getDraftValue(item, field.key);
      const serverValue = getSuggestedValue(item, field.key);
      if (draftValue !== serverValue) {
        revisedData[field.key] = draftValue;
      }
    });
    return Object.keys(revisedData).length > 0 ? revisedData : undefined;
  };

  const approvedCount = items.filter((item) => item.status === 'approved' && hasActionableSuggestion(item, targetFields)).length;
  const rejectedCount = items.filter((item) => item.status === 'rejected' && hasActionableSuggestion(item, targetFields)).length;
  const pendingItems = items.filter((item) =>
    (item.status === 'analyzed' || item.status === 'pending') && hasActionableSuggestion(item, targetFields)
  );
  const pendingDecision = pendingItems.length;

  return (
    <div className="space-y-4">
      <div
        className="flex items-center justify-between rounded-xl px-5 py-3"
        style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center gap-4">
          <span className="text-[13px]" style={{ color: 'var(--color-text-secondary)' }}>
            {analysisComplete ? 'Analiz tamamlandı' : `Analiz ediliyor... (${job.processed_count}/${job.total_count})`}
          </span>
          <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            {approvedCount} onaylandı · {pendingDecision} bekliyor
            {rejectedCount > 0 && ` · ${rejectedCount} reddedildi`}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {!analysisComplete && onStop && (
            <button
              type="button"
              onClick={onStop}
              className="rounded-lg px-3 py-1.5 text-[12px] font-medium transition hover:opacity-80"
              style={{
                background: 'rgba(239,68,68,0.1)',
                border: '1px solid rgba(239,68,68,0.3)',
                color: '#ef4444',
              }}
            >
              Analizi Durdur
            </button>
          )}

          {pendingDecision > 0 && (
            <button
              type="button"
              disabled={isMutating}
              onClick={() => {
                const pendingWithEdits = pendingItems.filter((item) => !!getItemRevisedData(item));
                if (pendingWithEdits.length === 0 && onBulkDecision && pendingItems.length > 1) {
                  onBulkDecision(pendingItems.map((item) => item.id), 'approved');
                  return;
                }

                pendingItems.forEach((item) => {
                  const revisedData = getItemRevisedData(item);
                  onDecision(item.id, revisedData ? 'revised' : 'approved', revisedData);
                });
              }}
              className="rounded-lg px-3 py-1.5 text-[12px] font-medium text-white transition hover:opacity-80 disabled:opacity-40"
              style={{ background: '#22c55e' }}
            >
              Tümünü Onayla
            </button>
          )}

          {analysisComplete && approvedCount > 0 && (
            <button
              type="button"
              disabled={isMutating}
              onClick={onApplyAll}
              className="rounded-lg px-4 py-1.5 text-[12px] font-semibold text-white transition hover:opacity-80 disabled:opacity-40"
              style={{ background: '#6366f1' }}
            >
              {isMutating ? 'Bekleyin...' : `${approvedCount} Ürünü Uygula`}
            </button>
          )}
        </div>
      </div>

      {!analysisComplete && job.total_count > 0 && (
        <div className="h-1.5 overflow-hidden rounded-full" style={{ background: 'var(--color-border)' }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${(job.processed_count / job.total_count) * 100}%`,
              background: '#6366f1',
            }}
          />
        </div>
      )}

      <div className="space-y-3">
        {visibleItems.map((item) => (
          <ItemCard
            key={item.id}
            item={item}
            analysisComplete={analysisComplete}
            targetFields={targetFields}
            regeneratingKey={regeneratingKey}
            getDraftValue={(fieldKey) => getDraftValue(item, fieldKey)}
            getItemRevisedData={() => getItemRevisedData(item)}
            onDraftChange={(fieldKey, next) => setDraftValue(item.id, fieldKey, next)}
            onDecision={(decision, revisedData) => onDecision(item.id, decision, revisedData)}
            onRegenerate={() => {
              resetDraftsForItem(item);
              onRegenerate(item.id);
            }}
            onFieldRegenerate={(fieldKey) => {
              setDraftValue(item.id, fieldKey, getSuggestedValue(item, fieldKey));
              onFieldRegenerate(item.id, fieldKey);
            }}
          />
        ))}
      </div>

      {analysisComplete && pendingDecision === 0 && approvedCount === 0 && onBack && (
        <div
          className="rounded-xl p-6 text-center"
          style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-border)' }}
        >
          <p className="text-[13px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Onaylanacak öneri bulunamadı.
          </p>
          <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            AI bu ürünler için öneri oluşturamadı veya tüm öneriler reddedildi.
            Farklı ürünler seçerek tekrar deneyebilirsiniz.
          </p>
          <button
            type="button"
            onClick={onBack}
            className="mt-4 rounded-lg px-4 py-2 text-[13px] font-medium text-white transition hover:opacity-80"
            style={{ background: '#6366f1' }}
          >
            Ürün Seçimine Dön
          </button>
        </div>
      )}
    </div>
  );
}

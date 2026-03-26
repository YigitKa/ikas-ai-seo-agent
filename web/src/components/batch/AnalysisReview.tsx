import { Suspense, lazy, useEffect, useRef, useState, type ReactNode } from 'react';
import type { BatchItem, BatchJob } from '../../types';

const RichTextHtmlEditor = lazy(() => import('./RichTextHtmlEditor'));

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
type Tone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger';

const DIFF_FIELDS: DiffField[] = [
  { key: 'name', label: 'Başlık' },
  { key: 'meta_title', label: 'Meta Başlık' },
  { key: 'meta_description', label: 'Meta Açıklama', multiline: true },
  { key: 'description', label: 'Açıklama', richText: true, multiline: true },
  { key: 'description_en', label: 'Açıklama (EN)', richText: true, multiline: true },
];

const ALLOWED_HTML_TAGS = new Set([
  'p',
  'br',
  'ul',
  'ol',
  'li',
  'strong',
  'em',
  'b',
  'i',
  'u',
  'span',
  'div',
  'h2',
  'h3',
  'h4',
  'a',
  'blockquote',
  'pre',
  'code',
  'hr',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
  'img',
]);

const TONE_STYLES: Record<Tone, { background: string; border: string; color: string }> = {
  neutral: {
    background: 'rgba(15,23,42,0.5)',
    border: '1px solid rgba(148,163,184,0.14)',
    color: 'var(--color-text-secondary)',
  },
  primary: {
    background: 'rgba(59,130,246,0.12)',
    border: '1px solid rgba(96,165,250,0.22)',
    color: '#dbeafe',
  },
  success: {
    background: 'rgba(16,185,129,0.14)',
    border: '1px solid rgba(16,185,129,0.28)',
    color: '#a7f3d0',
  },
  warning: {
    background: 'rgba(245,158,11,0.14)',
    border: '1px solid rgba(245,158,11,0.28)',
    color: '#fde68a',
  },
  danger: {
    background: 'rgba(239,68,68,0.14)',
    border: '1px solid rgba(239,68,68,0.28)',
    color: '#fecaca',
  },
};

const ITEM_STATUS_META: Record<string, { label: string; tone: Tone }> = {
  pending: { label: 'Sırada', tone: 'warning' },
  analyzed: { label: 'İncelenecek', tone: 'primary' },
  processing: { label: 'İşleniyor', tone: 'warning' },
  approved: { label: 'Onaylandı', tone: 'success' },
  rejected: { label: 'Reddedildi', tone: 'danger' },
  applied: { label: 'Uygulandı', tone: 'success' },
  skipped: { label: 'Atlandı', tone: 'warning' },
  failed: { label: 'Hata', tone: 'danger' },
  rolled_back: { label: 'Geri Alındı', tone: 'neutral' },
};

function classNames(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ');
}

function hasHtmlMarkup(value: string): boolean {
  return /<[^>]+>/.test(value);
}

function isSafeUrl(rawValue: string): boolean {
  const value = rawValue.trim();
  if (!value) return false;
  if (value.startsWith('/')) return true;

  try {
    const url = new URL(value);
    return ['http:', 'https:', 'mailto:', 'tel:'].includes(url.protocol);
  } catch {
    return false;
  }
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
      if (attribute.name.startsWith('on') || attribute.name === 'class' || attribute.name === 'color' || attribute.name === 'size' || attribute.name === 'face') {
        element.removeAttribute(attribute.name);
        return;
      }

      if (attribute.name === 'style') {
        const allowedStyles = attribute.value
          .split(';')
          .map((rule) => rule.trim())
          .filter(Boolean)
          .filter((rule) => /^text-align\s*:\s*(left|center|right|justify)$/i.test(rule));

        if (allowedStyles.length === 0) {
          element.removeAttribute('style');
        } else {
          element.setAttribute('style', allowedStyles.join('; '));
        }
        return;
      }

      if ((attribute.name === 'href' || attribute.name === 'src') && !isSafeUrl(attribute.value)) {
        element.removeAttribute(attribute.name);
        return;
      }

      if (attribute.name === 'target' && attribute.value !== '_blank') {
        element.removeAttribute(attribute.name);
        return;
      }

      if (attribute.name === 'rel' && !element.getAttribute('href')) {
        element.removeAttribute(attribute.name);
        return;
      }

      if ((attribute.name === 'colspan' || attribute.name === 'rowspan') && !/^\d+$/.test(attribute.value)) {
        element.removeAttribute(attribute.name);
      }
    });
  });
  return doc.body.innerHTML;
}

function formatCount(value: number): string {
  return value.toLocaleString('tr-TR');
}

function getFieldLabel(fieldKey: string): string {
  return DIFF_FIELDS.find((field) => field.key === fieldKey)?.label ?? fieldKey;
}

function getCharacterLabel(value: string): string {
  return `${formatCount(value.trim().length)} karakter`;
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
        style={{ color: emphasized ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}
        dangerouslySetInnerHTML={{ __html: sanitizeHtmlPreview(value) }}
      />
    );
  }

  return (
    <p
      className="text-[12px] leading-relaxed whitespace-pre-wrap"
      style={{ color: emphasized ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}
    >
      {value}
    </p>
  );
}

function InfoPill({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={classNames('inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]', className)}
      style={TONE_STYLES[tone]}
    >
      {children}
    </span>
  );
}

function MetricTile({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: Tone;
}) {
  const toneStyle = TONE_STYLES[tone];
  return (
    <div
      className="rounded-md px-2.5 py-1.5"
      style={{
        background: toneStyle.background,
        border: toneStyle.border,
      }}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>
        {label}
      </p>
      <p className="mt-0.5 text-[16px] font-semibold tabular-nums" style={{ color: toneStyle.color }}>
        {value}
      </p>
    </div>
  );
}

function FieldPane({
  label,
  helper,
  className,
  children,
}: {
  label: string;
  helper?: string;
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={classNames('min-w-0', className)}>
      <div className="mb-1 flex items-baseline gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.1em]" style={{ color: 'var(--color-text-muted)' }}>
          {label}
        </p>
        {helper && (
          <p className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
            {helper}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  tone = 'neutral',
  size = 'md',
  className,
  title,
}: {
  children: string;
  onClick?: () => void;
  disabled?: boolean;
  tone?: Tone;
  size?: 'sm' | 'md';
  className?: string;
  title?: string;
}) {
  const toneStyle =
    tone === 'success'
      ? {
          background: '#16a34a',
          border: '1px solid rgba(74,222,128,0.22)',
          color: '#f8fafc',
        }
      : tone === 'primary'
        ? {
            background: 'rgba(79,70,229,0.9)',
            border: '1px solid rgba(125,211,252,0.26)',
            color: '#eff6ff',
          }
        : TONE_STYLES[tone];

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={classNames(
        size === 'sm'
          ? 'rounded px-2 py-1 text-[10px] font-semibold'
          : 'rounded-md px-2.5 py-1.5 text-[11px] font-semibold',
        'transition duration-200 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-45',
        className,
      )}
      style={toneStyle}
    >
      {children}
    </button>
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
      className="rounded-lg px-2.5 py-1 text-[11px] font-semibold transition hover:-translate-y-0.5"
      style={{
        background: 'rgba(59,130,246,0.1)',
        border: '1px solid rgba(96,165,250,0.2)',
        color: '#bfdbfe',
      }}
    >
      {children}
    </button>
  );
}

function LegacyHtmlEditor({
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
    <div className="space-y-2.5">
      <div className="flex flex-wrap gap-1.5">
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
        rows={8}
        disabled={disabled}
        className="enterprise-input w-full resize-y rounded-xl px-3 py-2.5 font-mono text-[12px] leading-relaxed outline-none"
        style={{
          minHeight: 176,
          background: 'rgba(8,15,30,0.88)',
          border: '1px solid rgba(16,185,129,0.26)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)',
        }}
      />
    </div>
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
  return (
    <Suspense
      fallback={(
        <div
          className="rounded-md border px-2.5 py-2"
          style={{
            background: 'rgba(8,15,30,0.88)',
            borderColor: 'rgba(16,185,129,0.26)',
            minHeight: 220,
          }}
        />
      )}
    >
      <RichTextHtmlEditor value={value} onChange={onChange} disabled={disabled} />
    </Suspense>
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
        className="enterprise-input w-full resize-y rounded-md px-2.5 py-2 text-[12px] leading-relaxed outline-none"
        style={{
          minHeight: 96,
          background: 'rgba(16,185,129,0.06)',
          border: '1px solid rgba(16,185,129,0.28)',
        }}
      />
    );
  }

  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      className="enterprise-input w-full rounded-md px-2.5 py-2 text-[12px] leading-relaxed outline-none"
      style={{
        minHeight: 44,
        background: 'rgba(16,185,129,0.06)',
        border: '1px solid rgba(16,185,129,0.28)',
      }}
    />
  );
}

function LegacyDiffRow({
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
  const showHtmlWarning = Boolean(field.richText && draftValue.trim() !== '' && !hasHtmlMarkup(draftValue));
  const [editorMode, setEditorMode] = useState<'rich' | 'html'>('rich');

  const borderStyle = '1px solid rgba(148,163,184,0.14)';

  return (
    <div
      className="border-t"
      style={{ borderColor: 'rgba(148,163,184,0.10)' }}
    >
      <div
        className="flex flex-wrap items-center justify-between gap-2 py-1.5"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em]" style={{ color: 'var(--color-text-secondary)' }}>
            {field.label}
          </span>
          {isDirty && <InfoPill tone="warning">Manuel Düzenleme</InfoPill>}
        </div>

        <ActionButton
          onClick={onRegenerate}
          disabled={disabled || isRegenerating}
          tone="primary"
          size="sm"
        >
          {isRegenerating ? 'Üretiliyor...' : 'Yeniden Üret'}
        </ActionButton>
      </div>

      <div className="pt-1.5 pb-2">
        {field.richText ? (
          <div className="grid gap-2 lg:grid-cols-2">
            <div className="min-w-0">
              <div className="mb-1 flex items-baseline gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.1em]" style={{ color: 'var(--color-text-muted)' }}>Mevcut</p>
                <p className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>{original.trim() ? getCharacterLabel(original) : 'Boş alan'}</p>
              </div>
              <div
                className="rounded-md px-2.5 py-2 text-[12px] leading-relaxed"
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: borderStyle,
                  color: 'var(--color-text-secondary)',
                  minHeight: 280,
                  maxHeight: 400,
                  overflowY: 'auto',
                }}
              >
                <HtmlPreview value={original} />
              </div>
            </div>

            <div className="min-w-0">
              <div className="mb-1 flex items-baseline justify-between gap-2">
                <div className="flex items-baseline gap-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.1em]" style={{ color: 'var(--color-text-muted)' }}>Önerilen</p>
                  <p className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>{getCharacterLabel(draftValue)} · düzenlenebilir</p>
                </div>
                <div className="flex items-center gap-0.5">
                  <button
                    type="button"
                    onClick={() => setEditorMode('rich')}
                    className="rounded px-1.5 py-0.5 text-[10px] font-medium transition"
                    style={{
                      background: editorMode === 'rich' ? 'rgba(99,102,241,0.18)' : 'transparent',
                      color: editorMode === 'rich' ? '#a5b4fc' : 'var(--color-text-muted)',
                      border: editorMode === 'rich' ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
                    }}
                  >
                    Normal
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditorMode('html')}
                    className="rounded px-1.5 py-0.5 text-[10px] font-medium transition"
                    style={{
                      background: editorMode === 'html' ? 'rgba(99,102,241,0.18)' : 'transparent',
                      color: editorMode === 'html' ? '#a5b4fc' : 'var(--color-text-muted)',
                      border: editorMode === 'html' ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
                    }}
                  >
                    HTML
                  </button>
                </div>
              </div>
              {editorMode === 'rich' ? (
                <HtmlEditor value={draftValue} onChange={onChange} disabled={disabled} />
              ) : (
                <textarea
                  value={draftValue}
                  onChange={(event) => onChange(event.target.value)}
                  disabled={disabled}
                  className="enterprise-input w-full resize-y rounded-md px-2.5 py-2 font-mono text-[11px] leading-relaxed outline-none"
                  style={{
                    minHeight: 280,
                    background: 'rgba(16,185,129,0.06)',
                    border: '1px solid rgba(16,185,129,0.28)',
                  }}
                />
              )}
              {showHtmlWarning && (
                <p className="mt-1.5 text-[11px]" style={{ color: '#f59e0b' }}>
                  HTML etiketi görünmüyor. Onaylamadan önce başlık, paragraf veya liste ekleyin.
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="grid gap-2 lg:grid-cols-2">
            <FieldPane
              label="Mevcut"
              helper={original.trim() ? getCharacterLabel(original) : 'Boş alan'}
            >
              <div
                className="rounded-md px-2.5 py-2 text-[12px] leading-relaxed whitespace-pre-wrap"
                style={{
                  background: 'rgba(255,255,255,0.02)',
                  border: borderStyle,
                  color: 'var(--color-text-secondary)',
                  minHeight: field.multiline ? 96 : 44,
                }}
              >
                {original || <span style={{ opacity: 0.45 }}>Boş</span>}
              </div>
            </FieldPane>

            <FieldPane
              label="Önerilen"
              helper={getCharacterLabel(draftValue)}
            >
              <PlainEditor value={draftValue} onChange={onChange} multiline={field.multiline} disabled={disabled} />
            </FieldPane>
          </div>
        )}
      </div>

      {fieldError && (
        <div
          className="border-t px-2.5 py-1.5 text-[11px]"
          style={{
            borderColor: 'rgba(245,158,11,0.24)',
            background: 'rgba(245,158,11,0.08)',
            color: '#fbbf24',
          }}
        >
          {fieldError}
        </div>
      )}
    </div>
  );
}

function LegacyScoreBadge({ before, after }: { before: number | null; after: number | null }) {
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

function ScoreBadge({ before, after }: { before: number | null; after: number | null }) {
  if (before == null || after == null) return null;
  const delta = after - before;
  const tone: Tone = delta > 0 ? 'success' : delta < 0 ? 'danger' : 'neutral';
  const toneStyle = TONE_STYLES[tone];

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-medium tabular-nums"
      style={{
        background: toneStyle.background,
        border: toneStyle.border,
        color: 'var(--color-text-primary)',
      }}
    >
      {before} <span style={{ color: 'var(--color-text-muted)' }}>→</span> {after}
      <span style={{ color: toneStyle.color, fontWeight: 700 }}>
        {delta > 0 ? '+' : ''}{delta}
      </span>
    </span>
  );
}

function ItemStatusBadge({ status }: { status: BatchItem['status'] }) {
  const meta = ITEM_STATUS_META[status] ?? { label: status, tone: 'neutral' as Tone };
  return <InfoPill tone={meta.tone}>{meta.label}</InfoPill>;
}

function LegacyItemCard({
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
  const dirtyCount = displayFields.filter((field) => getDraftValue(field.key) !== getSuggestedValue(item, field.key)).length;

  return (
    <div
      className="overflow-hidden rounded-lg border"
      style={{
        background: 'rgba(11,17,32,0.92)',
        borderColor: 'rgba(148,163,184,0.12)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      }}
    >
      <div
        className="flex flex-wrap items-start justify-between gap-3 px-3 py-2"
        style={{
          borderBottom: '1px solid rgba(148,163,184,0.10)',
          background: 'rgba(15,23,42,0.6)',
        }}
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-[14px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {item.product_name}
            </p>
            <ItemStatusBadge status={item.status} />
            <ScoreBadge before={item.score_before} after={item.score_after} />
          </div>

          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <InfoPill tone="neutral">#{item.product_id}</InfoPill>
            <InfoPill tone="primary">{displayFields.length} alan</InfoPill>
            {dirtyCount > 0 && <InfoPill tone="warning">{dirtyCount} manuel değişiklik</InfoPill>}
            {hasEdits && <InfoPill tone="success">Revize ile onaylanacak</InfoPill>}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {item.status === 'approved' && !hasEdits && (
            <ActionButton
              onClick={() => onDecision('rejected')}
              disabled={isProcessing}
              tone="success"
              size="sm"
              title="Kararı değiştir"
              className="rounded-full"
            >
              Onaylandı
            </ActionButton>
          )}

          {item.status === 'rejected' && !hasEdits && (
            <ActionButton
              onClick={() => onDecision('approved')}
              disabled={isProcessing}
              tone="danger"
              size="sm"
              title="Kararı değiştir"
              className="rounded-full"
            >
              Reddedildi
            </ActionButton>
          )}

          {(item.status === 'analyzed' || item.status === 'pending' || hasEdits || item.status === 'rejected') && hasSuggestion && (
            <>
              <ActionButton
                onClick={() => onDecision(approveDecision, revisedData)}
                disabled={isProcessing}
                tone="success"
              >
                {hasEdits ? 'Düzenleyip Onayla' : 'Onayla'}
              </ActionButton>
              <ActionButton
                onClick={() => onDecision('rejected')}
                disabled={isProcessing}
                tone="danger"
              >
                Reddet
              </ActionButton>
            </>
          )}

          {canRegenerateWholeItem && (
            <ActionButton
              onClick={onRegenerate}
              disabled={isProcessing}
              tone="primary"
            >
              {isItemRegenerating ? 'Yeniden Üretiliyor...' : 'Tüm Alanları Yeniden Üret'}
            </ActionButton>
          )}
        </div>
      </div>

      <div className="space-y-0 px-3 py-2">
        {isProcessing && (
          <div
            className="flex items-center gap-2 rounded px-2.5 py-1.5"
            style={{
              background: 'rgba(59,130,246,0.08)',
              border: '1px solid rgba(96,165,250,0.16)',
            }}
          >
            <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="#60a5fa" strokeWidth={2}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            <span className="text-[12px]" style={{ color: '#bfdbfe' }}>
              AI alanları yeniden üretiyor.
            </span>
          </div>
        )}

        {noSuggestion && (
          <div
            className="rounded px-2.5 py-1.5 text-[12px]"
            style={{
              background: 'rgba(148,163,184,0.08)',
              border: '1px solid rgba(148,163,184,0.16)',
              color: 'var(--color-text-secondary)',
            }}
          >
            Seçili alanlar için henüz öneri yok. Her alan için ayrı yeniden üret kullanılabilir.
          </div>
        )}

        {item.status === 'failed' && (
          <div
            className="rounded px-2.5 py-1.5 text-[12px]"
            style={{
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.18)',
              color: '#fca5a5',
            }}
          >
            Hata: {item.skip_reason || 'Bilinmeyen hata'}
          </div>
        )}

        {item.status === 'skipped' && (
          <div
            className="rounded px-2.5 py-1.5 text-[12px]"
            style={{
              background: 'rgba(245,158,11,0.08)',
              border: '1px solid rgba(245,158,11,0.18)',
              color: '#fcd34d',
            }}
          >
            Atlandı: {item.skip_reason || 'AI bu ürün için öneri oluşturamadı.'}
          </div>
        )}

        {displayFields.length > 0 && (
          <div className="space-y-2.5">
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
    </div>
  );
}

function LegacyAnalysisReview({
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

void LegacyDiffRow;
void LegacyScoreBadge;
void LegacyItemCard;
void LegacyAnalysisReview;
void LegacyHtmlEditor;

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
  const exceptionCount = items.filter((item) => item.status === 'failed' || item.status === 'skipped').length;
  const reviewableCount = visibleItems.filter((item) => hasActionableSuggestion(item, targetFields)).length;
  const progress = job.total_count > 0 ? Math.min(100, Math.round((job.processed_count / job.total_count) * 100)) : 0;
  const targetFieldLabels = targetFields.map(getFieldLabel);

  return (
    <div className="space-y-3 pb-4">
      <div className="sticky top-0 z-20">
        <div
          className="overflow-hidden rounded-lg border"
          style={{
            background: 'rgba(15,23,42,0.95)',
            borderColor: 'rgba(148,163,184,0.14)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
            backdropFilter: 'blur(12px)',
          }}
        >
          <div className="grid gap-3 px-3 py-2 xl:grid-cols-[minmax(0,1fr)_auto]">
            <div className="grid gap-2 xl:grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,0.7fr))]">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <InfoPill tone={analysisComplete ? 'success' : 'warning'}>
                    {analysisComplete ? 'Analiz Hazır' : 'Analiz Sürüyor'}
                  </InfoPill>
                  <InfoPill tone="primary">{formatCount(job.total_count)} ürün</InfoPill>
                  <InfoPill tone="neutral">{targetFields.length} hedef alan</InfoPill>
                </div>

                <p className="mt-1.5 text-[14px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {analysisComplete ? 'Karar ve uygulama masası' : 'Diff akışı hazırlanıyor'}
                </p>
                <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
                  {analysisComplete
                    ? `${approvedCount} onaylandı, ${pendingDecision} ürün karar bekliyor${rejectedCount > 0 ? `, ${rejectedCount} reddedildi` : ''}.`
                    : `${formatCount(job.processed_count)} / ${formatCount(job.total_count)} ürün işlendi. İnceleme kartları canlı güncelleniyor.`}
                </p>
              </div>

              <MetricTile
                label="İncelenen"
                value={`${formatCount(job.processed_count)}/${formatCount(job.total_count)}`}
                tone="primary"
              />
              <MetricTile label="Bekleyen" value={formatCount(pendingDecision)} tone="warning" />
              <MetricTile label="Onaylanan" value={formatCount(approvedCount)} tone="success" />
              <MetricTile label="İstisna" value={formatCount(exceptionCount)} tone={exceptionCount > 0 ? 'danger' : 'neutral'} />
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              {!analysisComplete && onStop && (
                <ActionButton onClick={onStop} tone="danger">
                  Analizi Durdur
                </ActionButton>
              )}

              {pendingDecision > 0 && (
                <ActionButton
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
                  tone="success"
                >
                  Tümünü Onayla
                </ActionButton>
              )}

              {analysisComplete && approvedCount > 0 && (
                <ActionButton
                  disabled={isMutating}
                  onClick={onApplyAll}
                  tone="primary"
                >
                  {isMutating ? 'Bekleyin...' : `${approvedCount} Ürünü Uygula`}
                </ActionButton>
              )}
            </div>
          </div>

          <div
            className="flex flex-wrap items-center gap-1.5 border-t px-3 py-1.5"
            style={{ borderColor: 'rgba(148,163,184,0.10)' }}
          >
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: 'var(--color-text-muted)' }}>
              Hedef Alanlar
            </span>
            {targetFieldLabels.map((label) => (
              <InfoPill key={label} tone="neutral">
                {label}
              </InfoPill>
            ))}
            <div className="ml-auto">
              <InfoPill tone="primary">{formatCount(reviewableCount)} önerili ürün</InfoPill>
            </div>
          </div>

          {!analysisComplete && job.total_count > 0 && (
            <div
              className="flex items-center gap-2 border-t px-3 py-1.5"
              style={{ borderColor: 'rgba(148,163,184,0.10)' }}
            >
              <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: 'rgba(148,163,184,0.14)' }}>
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${progress}%`,
                    background: 'linear-gradient(90deg, #f59e0b, #3b82f6)',
                  }}
                />
              </div>
              <span className="text-[11px] font-semibold tabular-nums" style={{ color: 'var(--color-text-secondary)' }}>
                %{progress}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2">
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
          className="rounded-lg border px-4 py-5 text-center"
          style={{
            background: 'rgba(15,23,42,0.9)',
            borderColor: 'rgba(148,163,184,0.14)',
          }}
        >
          <p className="text-[14px] font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
            Onaylanacak öneri bulunamadı.
          </p>
          <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
            AI bu ürünler için öneri oluşturamadı veya tüm öneriler reddedildi. Farklı ürünlerle yeniden deneyin.
          </p>
          <div className="mt-4 flex justify-center">
            <ActionButton onClick={onBack} tone="primary">
              Ürün Seçimine Dön
            </ActionButton>
          </div>
        </div>
      )}
    </div>
  );
}

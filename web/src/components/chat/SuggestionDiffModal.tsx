import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Product, SeoSuggestion } from "../../types";

interface DiffField {
  key: keyof SeoSuggestion;
  originalKey: keyof SeoSuggestion;
  label: string;
  multiline: boolean;
}

const DIFF_FIELDS: DiffField[] = [
  { key: "suggested_name", originalKey: "original_name", label: "Urun Adi", multiline: false },
  { key: "suggested_meta_title", originalKey: "original_meta_title", label: "Meta Title", multiline: false },
  { key: "suggested_meta_description", originalKey: "original_meta_description", label: "Meta Description", multiline: true },
  { key: "suggested_description", originalKey: "original_description", label: "Aciklama (TR)", multiline: true },
  { key: "suggested_description_en", originalKey: "original_description_en", label: "Aciklama (EN)", multiline: true },
];

function stripHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body.textContent ?? "";
}

function sanitizeHtml(html: string): string {
  // basic, synchronous cleanup for trusted panel content; strips script/style tags.
  return html.replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, "");
}

function Chip({ label }: { label: string }) {
  return (
    <span
      className="rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide"
      style={{
        background: "var(--alpha-white-6)",
        border: "1px solid var(--alpha-white-12)",
        color: "var(--color-text-secondary)",
      }}
    >
      {label}
    </span>
  );
}

function RichTextEditor({
  value,
  onChange,
  minRows = 8,
}: {
  value: string;
  onChange: (next: string) => void;
  minRows?: number;
}) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const wrapSelection = (prefix: string, suffix = prefix) => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const { selectionStart, selectionEnd } = textarea;
    const text = textarea.value;
    const selected = text.slice(selectionStart, selectionEnd) || "";
    const nextValue = `${text.slice(0, selectionStart)}${prefix}${selected}${suffix}${text.slice(selectionEnd)}`;
    onChange(nextValue);
    queueMicrotask(() => {
      const caret = selectionEnd + prefix.length + suffix.length;
      textarea.focus();
      textarea.setSelectionRange(caret, caret);
    });
  };

  const applyList = (ordered = false) => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const { selectionStart, selectionEnd } = textarea;
    const text = textarea.value;
    const selected = (selectionStart === selectionEnd ? text : text.slice(selectionStart, selectionEnd)) || "";
    const lines = selected.split("\n").map((line, idx) => {
      const content = line.replace(/^([*>-]|\d+\.)\s*/, "").trim();
      if (!content && selected.length === 0) return ordered ? `${idx + 1}. ` : "- ";
      return ordered ? `${idx + 1}. ${content}` : `- ${content}`;
    });
    const formatted = lines.join("\n");
    const nextValue = `${text.slice(0, selectionStart)}${formatted}${text.slice(selectionEnd || text.length)}`;
    onChange(nextValue);
    queueMicrotask(() => {
      const caret = selectionStart + formatted.length;
      textarea.focus();
      textarea.setSelectionRange(caret, caret);
    });
  };

  const wordCount = value.trim().split(/\s+/).filter(Boolean).length || 0;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => wrapSelection("**")}
          className="rounded-md px-2 py-1 text-[11px] font-semibold"
          style={{ background: "var(--alpha-white-6)", border: "1px solid var(--alpha-white-8)", color: "var(--color-text-primary)" }}
        >
          Kalın
        </button>
        <button
          type="button"
          onClick={() => wrapSelection("_")}
          className="rounded-md px-2 py-1 text-[11px] font-semibold"
          style={{ background: "var(--alpha-white-6)", border: "1px solid var(--alpha-white-8)", color: "var(--color-text-primary)" }}
        >
          İtalik
        </button>
        <button
          type="button"
          onClick={() => applyList(false)}
          className="rounded-md px-2 py-1 text-[11px] font-semibold"
          style={{ background: "var(--alpha-white-6)", border: "1px solid var(--alpha-white-8)", color: "var(--color-text-primary)" }}
        >
          Madde
        </button>
        <button
          type="button"
          onClick={() => applyList(true)}
          className="rounded-md px-2 py-1 text-[11px] font-semibold"
          style={{ background: "var(--alpha-white-6)", border: "1px solid var(--alpha-white-8)", color: "var(--color-text-primary)" }}
        >
          Sıralı
        </button>
        <button
          type="button"
          onClick={() => wrapSelection("[", "](url)")}
          className="rounded-md px-2 py-1 text-[11px] font-semibold"
          style={{ background: "var(--alpha-white-6)", border: "1px solid var(--alpha-white-8)", color: "var(--color-text-primary)" }}
        >
          Link
        </button>
        <button
          type="button"
          onClick={() => wrapSelection("> ", "")}
          className="rounded-md px-2 py-1 text-[11px] font-semibold"
          style={{ background: "var(--alpha-white-6)", border: "1px solid var(--alpha-white-8)", color: "var(--color-text-primary)" }}
        >
          Alıntı
        </button>
        <Chip label={`${wordCount} kelime`} />
      </div>

      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={minRows}
        className="w-full resize-y rounded-lg px-3 py-2 text-[12px] leading-relaxed outline-none"
        style={{
          background: "var(--tint-success-bg)",
          border: "1px solid var(--color-border-success)",
          color: "var(--color-text-primary)",
        }}
      />
    </div>
  );
}

function FieldDiff({
  field,
  original,
  editedValue,
  onEdit,
  isIncluded,
  onToggleInclude,
}: {
  field: DiffField;
  original: string;
  editedValue: string;
  onEdit: (value: string) => void;
  isIncluded: boolean;
  onToggleInclude: () => void;
}) {
  if (!editedValue) return null;

  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");
  const displayOriginal = original.length > 300 ? stripHtml(original) : original;
  const truncatedOriginal = displayOriginal.length > 220 ? `${displayOriginal.slice(0, 220)}...` : displayOriginal;
  const originalWordCount = truncatedOriginal.trim().length === 0 ? 0 : truncatedOriginal.trim().split(/\s+/).length;
  const suggestedWordCount = editedValue.trim().length === 0 ? 0 : editedValue.trim().split(/\s+/).length;
  const looksLikeHtml = /<[^>]+>/.test(editedValue);

  return (
    <div
      className="rounded-xl p-4 transition-opacity"
      style={{
        background: "linear-gradient(140deg, var(--alpha-white-3), var(--alpha-white-3))",
        border: `1px solid ${isIncluded ? "var(--alpha-white-12)" : "var(--alpha-white-6)"}`,
        opacity: isIncluded ? 1 : 0.45,
      }}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={isIncluded}
            onChange={onToggleInclude}
            className="h-3.5 w-3.5 cursor-pointer rounded accent-emerald-500"
          />
          <div>
            <span className="block text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
              {field.label}
            </span>
            <div className="mt-1 flex flex-wrap gap-2">
              <Chip label={`Mevcut ${originalWordCount} kelime`} />
              <Chip label={`Öneri ${suggestedWordCount} kelime`} />
              {field.multiline && <Chip label="Zengin editör" />}
            </div>
          </div>
        </label>
        <div className="flex items-center gap-2">
          <Chip label={isIncluded ? "Onaya dahil" : "Hariç"} />
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <div className="mb-1 text-[10px] font-medium" style={{ color: "rgba(239, 68, 68, 0.7)" }}>
            MEVCUT
          </div>
          <div
            className="rounded-lg px-3 py-2 text-[12px] leading-relaxed"
            style={{
              background: "var(--tint-danger-bg)",
              border: "1px solid var(--tint-danger-soft)",
              color: "var(--color-text-secondary)",
              minHeight: 110,
            }}
          >
            {truncatedOriginal ? (
              <div className="text-[12px] leading-relaxed" style={{ color: "var(--color-text-secondary)" }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{truncatedOriginal}</ReactMarkdown>
              </div>
            ) : (
              <span style={{ color: "var(--color-text-muted)" }}>(boş)</span>
            )}
          </div>
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between text-[10px] font-medium" style={{ color: "rgba(34, 197, 94, 0.7)" }}>
            <span>ÖNERİLEN</span>
            <Chip label={viewMode === "edit" ? "Düzenleme açık" : "Önizleme"} />
          </div>

          {viewMode === "edit" && isIncluded ? (
            field.multiline ? (
              <RichTextEditor value={editedValue} onChange={onEdit} />
            ) : (
              <input
                value={editedValue}
                onChange={(e) => onEdit(e.target.value)}
                className="w-full rounded-lg px-3 py-2 text-[12px] leading-relaxed outline-none"
                style={{
                  background: "var(--tint-success-bg)",
                  border: "1px solid var(--color-border-success)",
                  color: "var(--color-text-primary)",
                }}
              />
            )
          ) : (
            <div
              className="rounded-lg border px-3 py-2 text-[12px] leading-relaxed"
              style={{
                background: "var(--tint-success-bg)",
                borderColor: "var(--color-border-success)",
                color: isIncluded ? "var(--color-text-primary)" : "var(--color-text-muted)",
                textDecoration: isIncluded ? "none" : "line-through",
                minHeight: 110,
              }}
            >
              {viewMode === "edit" ? (
                field.multiline ? (
                  <RichTextEditor value={editedValue} onChange={onEdit} />
                ) : (
                  <input
                    value={editedValue}
                    onChange={(e) => onEdit(e.target.value)}
                    className="w-full rounded-lg px-3 py-2 text-[12px] leading-relaxed outline-none"
                    style={{
                      background: "var(--tint-success-bg)",
                      border: "1px solid var(--color-border-success)",
                      color: "var(--color-text-primary)",
                    }}
                  />
                )
              ) : looksLikeHtml ? (
                <div
                  className="prose prose-invert max-w-none text-[13px] leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: sanitizeHtml(editedValue) }}
                />
              ) : (
                <div className="prose prose-invert max-w-none text-[13px] leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {editedValue.length > 2000 ? `${editedValue.slice(0, 2000)}...` : editedValue}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => setViewMode("edit")}
          className="rounded-md px-3 py-1.5 text-[11px] font-semibold transition-all"
          style={{
            background: viewMode === "edit" ? "var(--tint-primary-soft)" : "var(--alpha-white-6)",
            border: "1px solid var(--alpha-white-12)",
            color: viewMode === "edit" ? "#c4c7ff" : "var(--color-text-secondary)",
          }}
        >
          Düzenle
        </button>
        <button
          type="button"
          onClick={() => setViewMode("preview")}
          className="rounded-md px-3 py-1.5 text-[11px] font-semibold transition-all"
          style={{
            background: viewMode === "preview" ? "var(--color-border-success)" : "var(--alpha-white-6)",
            border: "1px solid var(--alpha-white-12)",
            color: viewMode === "preview" ? "var(--color-text-success-soft)" : "var(--color-text-secondary)",
          }}
        >
          Formatlı Önizleme
        </button>
      </div>
    </div>
  );
}

export default function SuggestionDiffModal({
  suggestion,
  product,
  onApprove,
  onReject,
}: {
  suggestion: SeoSuggestion;
  product?: Product;
  onApprove: (editedSuggestion: SeoSuggestion) => void;
  onReject: () => void;
}) {
  const [editedSuggestion, setEditedSuggestion] = useState<SeoSuggestion>({ ...suggestion });
  const [excludedFields, setExcludedFields] = useState<Set<keyof SeoSuggestion>>(new Set());
  const [isFullscreen, setIsFullscreen] = useState(false);

  const handleEditField = (key: keyof SeoSuggestion, value: string) => {
    setEditedSuggestion((prev) => ({ ...prev, [key]: value }));
  };

  const toggleFieldInclude = (key: keyof SeoSuggestion) => {
    setExcludedFields((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleApprove = () => {
    const finalSuggestion = { ...editedSuggestion };
    for (const key of excludedFields) {
      (finalSuggestion as Record<keyof SeoSuggestion, unknown>)[key] = "";
    }
    onApprove(finalSuggestion);
  };

  const visibleFields = DIFF_FIELDS.filter((field) => {
    const value = suggestion[field.key];
    return typeof value === "string" && value.trim().length > 0;
  });

  const includedCount = visibleFields.filter((f) => !excludedFields.has(f.key)).length;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0, 0, 0, 0.64)", backdropFilter: "blur(6px)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onReject();
      }}
    >
      <div
        className="relative mx-4 flex max-h-[90vh] w-full flex-col overflow-hidden rounded-2xl"
        style={{
          background: "var(--color-bg-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 30px 80px rgba(0, 0, 0, 0.65)",
          maxWidth: isFullscreen ? "min(1400px, 96vw)" : "1100px",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute inset-x-0 top-0 h-1" style={{ background: "linear-gradient(90deg, var(--color-orange), var(--color-success))" }} />

        <div
          className="flex flex-wrap items-center justify-between gap-3 px-6 py-4"
          style={{ borderBottom: "1px solid var(--color-border)" }}
        >
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--color-text-primary)" }}>
              Değişiklikleri İncele ve Onayla
            </h2>
            <p className="mt-0.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
              {product?.name ?? suggestion.original_name ?? "Ürün"} · Bu ekran canlı veriyi güncelleyecek onay adımıdır.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsFullscreen((p) => !p)}
              className="rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-all hover:opacity-85"
              style={{
                background: "var(--alpha-white-6)",
                border: "1px solid var(--alpha-white-12)",
                color: "var(--color-text-primary)",
              }}
            >
              {isFullscreen ? "Pencereyi Daralt" : "Tam Ekran"}
            </button>
            <button
              type="button"
              onClick={onReject}
              className="rounded-lg p-1.5 transition-all hover:opacity-70"
              style={{ color: "var(--color-text-muted)" }}
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div
          className="grid gap-3 px-6 py-3 md:grid-cols-3"
          style={{ borderBottom: "1px solid var(--color-border)", background: "rgba(255,140,0,0.06)" }}
        >
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400 shadow-[0_0_0_6px_rgba(251,191,36,0.25)]" />
            <div>
              <p className="text-xs font-semibold" style={{ color: "var(--color-icon-warning)" }}>
                Kritik 
              </p>
              <p className="text-[11px]" style={{ color: "var(--color-text-secondary)" }}>
                Kaydettiğiniz anda canlıya yazılır. Gerekirse alanları tek tek hariç bırakın.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 md:justify-center">
            <Chip label={`${includedCount}/${visibleFields.length || 0} alan seçili`} />
            <Chip label="Önce oku, sonra onayla" />
          </div>
          <div className="flex items-center justify-end gap-2 text-[12px]" style={{ color: "var(--color-text-muted)" }}>
            <span>Bütün alanları kontrol edin.</span>
          </div>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-6 py-4">
          {visibleFields.map((field) => {
            const originalValue = String(suggestion[field.originalKey] ?? "");
            const suggestedValue = String(editedSuggestion[field.key] ?? "");

            return (
              <FieldDiff
                key={field.key}
                field={field}
                original={originalValue}
                editedValue={suggestedValue}
                onEdit={(v) => handleEditField(field.key, v)}
                isIncluded={!excludedFields.has(field.key)}
                onToggleInclude={() => toggleFieldInclude(field.key)}
              />
            );
          })}

          {visibleFields.length === 0 && (
            <div className="py-8 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
              Gösterilecek değişiklik bulunamadı.
            </div>
          )}
        </div>

        <div
          className="flex flex-wrap items-center justify-between gap-3 px-6 py-4"
          style={{ borderTop: "1px solid var(--color-border)" }}
        >
          <div className="flex items-center gap-2 text-[12px]" style={{ color: "var(--color-text-muted)" }}>
            <span>Önceki adım ile ilgili tereddütünüz varsa iptal edin.</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onReject}
              className="rounded-xl px-5 py-2.5 text-sm font-medium transition-all hover:opacity-80"
              style={{
                background: "var(--alpha-white-6)",
                border: "1px solid var(--alpha-white-12)",
                color: "var(--color-text-secondary)",
              }}
            >
              İptal
            </button>
            <button
              type="button"
              onClick={handleApprove}
              disabled={includedCount === 0}
              className="rounded-xl px-5 py-2.5 text-sm font-semibold transition-all hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                background: includedCount > 0 ? "linear-gradient(135deg, var(--color-success), var(--color-success))" : "rgba(255,255,255,0.1)",
                color: "white",
                boxShadow: includedCount > 0 ? "0 6px 16px var(--color-border-success)" : "none",
              }}
            >
              Onayla ve Uygula{includedCount < visibleFields.length ? ` (${includedCount}/${visibleFields.length})` : ""}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
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

function FieldDiff({
  field,
  original,
  suggested,
  editedValue,
  onEdit,
  isEditing,
  onToggleEdit,
}: {
  field: DiffField;
  original: string;
  suggested: string;
  editedValue: string;
  onEdit: (value: string) => void;
  isEditing: boolean;
  onToggleEdit: () => void;
}) {
  if (!suggested) return null;

  const displayOriginal = original.length > 300 ? stripHtml(original) : original;
  const truncatedOriginal = displayOriginal.length > 200
    ? displayOriginal.slice(0, 200) + "..."
    : displayOriginal;

  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--color-text-muted)" }}>
          {field.label}
        </span>
        <button
          type="button"
          onClick={onToggleEdit}
          className="rounded-md px-2 py-1 text-[11px] font-medium transition-all hover:opacity-80"
          style={{
            background: isEditing ? "rgba(99, 102, 241, 0.2)" : "rgba(255,255,255,0.06)",
            color: isEditing ? "#a5b4fc" : "var(--color-text-secondary)",
            border: `1px solid ${isEditing ? "rgba(99, 102, 241, 0.3)" : "rgba(255,255,255,0.1)"}`,
          }}
        >
          {isEditing ? "Tamam" : "Duzenle"}
        </button>
      </div>

      {/* Original */}
      <div className="mb-3">
        <div className="mb-1 text-[10px] font-medium" style={{ color: "rgba(239, 68, 68, 0.7)" }}>
          MEVCUT
        </div>
        <div
          className="rounded-lg px-3 py-2 text-[12px] leading-relaxed"
          style={{
            background: "rgba(239, 68, 68, 0.06)",
            border: "1px solid rgba(239, 68, 68, 0.12)",
            color: "var(--color-text-secondary)",
          }}
        >
          {truncatedOriginal || <span style={{ color: "var(--color-text-muted)" }}>(bos)</span>}
        </div>
      </div>

      {/* Suggested / Editable */}
      <div>
        <div className="mb-1 text-[10px] font-medium" style={{ color: "rgba(34, 197, 94, 0.7)" }}>
          ONERILEN
        </div>
        {isEditing ? (
          <textarea
            value={editedValue}
            onChange={(e) => onEdit(e.target.value)}
            rows={field.multiline ? 6 : 2}
            className="w-full resize-y rounded-lg px-3 py-2 text-[12px] leading-relaxed outline-none"
            style={{
              background: "rgba(34, 197, 94, 0.06)",
              border: "1px solid rgba(34, 197, 94, 0.25)",
              color: "var(--color-text-primary)",
              minHeight: field.multiline ? "120px" : "40px",
            }}
          />
        ) : (
          <div
            className="rounded-lg px-3 py-2 text-[12px] leading-relaxed"
            style={{
              background: "rgba(34, 197, 94, 0.06)",
              border: "1px solid rgba(34, 197, 94, 0.12)",
              color: "var(--color-text-primary)",
            }}
          >
            {editedValue.length > 300 ? editedValue.slice(0, 300) + "..." : editedValue}
          </div>
        )}
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
  const [editingField, setEditingField] = useState<string | null>(null);

  const handleEditField = (key: string, value: string) => {
    setEditedSuggestion((prev) => ({ ...prev, [key]: value }));
  };

  const visibleFields = DIFF_FIELDS.filter((field) => {
    const value = suggestion[field.key];
    return typeof value === "string" && value.trim().length > 0;
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0, 0, 0, 0.6)", backdropFilter: "blur(4px)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onReject();
      }}
    >
      <div
        className="relative mx-4 flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl"
        style={{
          background: "var(--color-bg-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "0 25px 50px rgba(0, 0, 0, 0.5)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4"
          style={{ borderBottom: "1px solid var(--color-border)" }}
        >
          <div>
            <h2 className="text-base font-semibold" style={{ color: "var(--color-text-primary)" }}>
              Degisiklikleri Incele
            </h2>
            <p className="mt-0.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
              {product?.name ?? suggestion.original_name ?? "Urun"} — Duzenleme yapabilir veya onaylayabilirsiniz
            </p>
          </div>
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

        {/* Body */}
        <div className="flex-1 space-y-3 overflow-y-auto px-6 py-4">
          {visibleFields.map((field) => {
            const originalValue = String(suggestion[field.originalKey] ?? "");
            const suggestedValue = String(editedSuggestion[field.key] ?? "");

            return (
              <FieldDiff
                key={field.key}
                field={field}
                original={originalValue}
                suggested={suggestedValue}
                editedValue={suggestedValue}
                onEdit={(v) => handleEditField(field.key, v)}
                isEditing={editingField === field.key}
                onToggleEdit={() =>
                  setEditingField((prev) => (prev === field.key ? null : field.key))
                }
              />
            );
          })}

          {visibleFields.length === 0 && (
            <div className="py-8 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
              Gosterilecek degisiklik bulunamadi.
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-3 px-6 py-4"
          style={{ borderTop: "1px solid var(--color-border)" }}
        >
          <button
            type="button"
            onClick={onReject}
            className="rounded-xl px-5 py-2.5 text-sm font-medium transition-all hover:opacity-80"
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "var(--color-text-secondary)",
            }}
          >
            Iptal
          </button>
          <button
            type="button"
            onClick={() => onApprove(editedSuggestion)}
            className="rounded-xl px-5 py-2.5 text-sm font-semibold transition-all hover:opacity-90"
            style={{
              background: "linear-gradient(135deg, #22c55e, #16a34a)",
              color: "white",
              boxShadow: "0 4px 12px rgba(34, 197, 94, 0.3)",
            }}
          >
            Onayla ve Uygula
          </button>
        </div>
      </div>
    </div>
  );
}

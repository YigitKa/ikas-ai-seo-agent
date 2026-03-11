import type { SeoSuggestion } from "../../types";

type PendingSuggestionAction =
  | "single_apply_meta"
  | "single_apply_content"
  | "single_apply_meta_content"
  | "single_apply_all";

type SuggestionFieldPreview = {
  key: string;
  label: string;
  original: string;
  suggested: string;
  group: "meta" | "content";
};

const SUGGESTION_FIELD_CONFIG = [
  {
    key: "suggested_name",
    label: "Urun Adi",
    originalKey: "original_name",
    group: "content",
  },
  {
    key: "suggested_meta_title",
    label: "Meta Title",
    originalKey: "original_meta_title",
    group: "meta",
  },
  {
    key: "suggested_meta_description",
    label: "Meta Description",
    originalKey: "original_meta_description",
    group: "meta",
  },
  {
    key: "suggested_description",
    label: "Aciklama (TR)",
    originalKey: "original_description",
    group: "content",
  },
  {
    key: "suggested_description_en",
    label: "Aciklama (EN)",
    originalKey: "original_description_en",
    group: "content",
  },
] as const;

function compactPreview(value: string | null | undefined) {
  const normalized = (value ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "-";
  }
  if (normalized.length <= 90) {
    return normalized;
  }
  return `${normalized.slice(0, 87)}...`;
}

function collectFieldPreviews(
  suggestion: SeoSuggestion | null,
): SuggestionFieldPreview[] {
  if (!suggestion) {
    return [];
  }

  return SUGGESTION_FIELD_CONFIG.reduce<SuggestionFieldPreview[]>(
    (items, field) => {
      const suggestedValue = compactPreview(
        suggestion[field.key as keyof SeoSuggestion] as string | null | undefined,
      );
      if (suggestedValue === "-") {
        return items;
      }

      items.push({
        key: field.key,
        label: field.label,
        original: compactPreview(
          suggestion[field.originalKey as keyof SeoSuggestion] as
            | string
            | null
            | undefined,
        ),
        suggested: suggestedValue,
        group: field.group,
      });
      return items;
    },
    [],
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
  emphasis = "secondary",
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  emphasis?: "primary" | "secondary";
}) {
  const isPrimary = emphasis === "primary";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded-xl px-3 py-2 text-[12px] font-semibold transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50"
      style={{
        background: isPrimary
          ? "linear-gradient(135deg, rgba(34, 197, 94, 0.18), rgba(16, 185, 129, 0.12))"
          : "rgba(255,255,255,0.04)",
        border: isPrimary
          ? "1px solid rgba(34, 197, 94, 0.28)"
          : "1px solid rgba(255,255,255,0.10)",
        color: isPrimary ? "#dcfce7" : "var(--color-text-primary)",
      }}
    >
      {label}
    </button>
  );
}

export default function PendingSuggestionPanel({
  suggestion,
  isLoading,
  onAction,
}: {
  suggestion: SeoSuggestion | null;
  isLoading?: boolean;
  onAction: (action: PendingSuggestionAction) => void;
}) {
  const fields = collectFieldPreviews(suggestion);
  const hasMeta = fields.some((field) => field.group === "meta");
  const hasContent = fields.some((field) => field.group === "content");

  return (
    <div
      className="mx-3 mt-3 rounded-2xl p-4"
      style={{
        background: suggestion
          ? "linear-gradient(145deg, rgba(16, 185, 129, 0.08), rgba(15, 23, 42, 0.94))"
          : "linear-gradient(145deg, rgba(255,255,255,0.035), rgba(15, 23, 42, 0.94))",
        border: suggestion
          ? "1px solid rgba(16, 185, 129, 0.18)"
          : "1px solid rgba(255,255,255,0.08)",
        boxShadow: suggestion ? "0 18px 40px rgba(16, 185, 129, 0.08)" : "none",
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.16em]"
            style={{
              color: suggestion ? "rgba(110, 231, 183, 0.88)" : "var(--color-text-muted)",
            }}
          >
            Pending Suggestion
          </div>
          <div className="mt-1 text-[15px] font-semibold text-white">
            {suggestion
              ? "Bekleyen degisiklikler hazir"
              : "Bekleyen degisiklik bulunmuyor"}
          </div>
        </div>
        {suggestion ? (
          <div
            className="rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]"
            style={{
              background: "rgba(16, 185, 129, 0.12)",
              color: "#86efac",
              border: "1px solid rgba(16, 185, 129, 0.22)",
            }}
          >
            Ready
          </div>
        ) : null}
      </div>

      {suggestion ? (
        <>
          <p
            className="mt-2 text-[12px] leading-relaxed"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Secili urun icin kayitli pending suggestion burada gorunur. Chat
            mesajinin icine bakmadan buradan dogrudan onaylayip uygulayabilirsin.
          </p>

          <div className="mt-4 space-y-2">
            {fields.map((field) => (
              <div
                key={field.key}
                className="rounded-xl px-3 py-2.5"
                style={{
                  background: "rgba(255,255,255,0.035)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <div className="text-[11px] font-semibold text-white">
                  {field.label}
                </div>
                <div
                  className="mt-1 text-[11px]"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  Mevcut: {field.original}
                </div>
                <div
                  className="mt-1 text-[12px]"
                  style={{ color: "#d1fae5" }}
                >
                  Uygulanacak: {field.suggested}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <div
              className="text-[11px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: "var(--color-text-muted)" }}
            >
              Secenekler
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {hasMeta ? (
                <ActionButton
                  label="Meta Alanlarini Uygula"
                  disabled={isLoading}
                  onClick={() => onAction("single_apply_meta")}
                />
              ) : null}
              {hasContent ? (
                <ActionButton
                  label="Icerik Alanlarini Uygula"
                  disabled={isLoading}
                  onClick={() => onAction("single_apply_content")}
                />
              ) : null}
              {hasMeta && hasContent ? (
                <ActionButton
                  label="Meta + Icerik"
                  disabled={isLoading}
                  onClick={() => onAction("single_apply_meta_content")}
                />
              ) : null}
              <ActionButton
                label="Degisiklikleri Uygula"
                disabled={isLoading}
                emphasis="primary"
                onClick={() => onAction("single_apply_all")}
              />
            </div>
          </div>
        </>
      ) : (
        <p
          className="mt-2 text-[12px] leading-relaxed"
          style={{ color: "var(--color-text-secondary)" }}
        >
          Chat icinde onayli SEO onerisi pending suggestion olarak kaydedildiginde
          bu panel otomatik acilir ve "Degisiklikleri Uygula" butonu burada gorunur.
        </p>
      )}
    </div>
  );
}

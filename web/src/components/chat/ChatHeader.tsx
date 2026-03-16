interface ChatHeaderProps {
  displayProductName?: string;
  displayProductCategory?: string | null;
  displaySeoScore?: number | null;
  productDetailUrl?: string;
  hasMessages: boolean;
  onClear: () => void;
  onExport: () => void;
}

export function ChatHeader({
  displayProductName,
  displayProductCategory,
  displaySeoScore,
  productDetailUrl,
  hasMessages,
  onClear,
  onExport,
}: ChatHeaderProps) {
  return (
    <div className="px-4 py-3" style={{ borderBottom: "1px solid rgba(148,163,184,0.16)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {displayProductName ? (
            <div className="min-w-0">
              <div
                className="text-[10px] font-semibold uppercase tracking-[0.18em]"
                style={{ color: "var(--color-text-muted)" }}
              >
                Aktif urun
              </div>
              <div className="flex items-center gap-2">
                <div className="truncate text-[18px] font-semibold text-white">
                  {displayProductName}
                </div>
                {productDetailUrl && (
                  <a
                    href={productDetailUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-shrink-0 rounded-md px-2 py-1 text-[10px] font-medium transition-opacity hover:opacity-80"
                    style={{
                      background: 'rgba(99, 102, 241, 0.12)',
                      color: '#c7d2fe',
                      border: '1px solid rgba(99, 102, 241, 0.2)',
                    }}
                    title="ikas urun detayina git"
                  >
                    ikas ↗
                  </a>
                )}
              </div>
              <div
                className="mt-1 text-[11px]"
                style={{ color: "var(--color-text-muted)" }}
              >
                {displayProductCategory || "Kategori yok"}
                {typeof displaySeoScore === "number"
                  ? ` | SEO ${displaySeoScore}/100`
                  : ""}
              </div>
            </div>
          ) : (
            <div className="min-w-0">
              <div
                className="text-[10px] font-semibold uppercase tracking-[0.18em]"
                style={{ color: "var(--color-text-muted)" }}
              >
                Sohbet
              </div>
              <div
                className="mt-1 text-[14px] font-semibold"
                style={{ color: "var(--color-text-primary)" }}
              >
                Bir urun secin veya mesaja baslayin
              </div>
            </div>
          )}
        </div>

        {hasMessages && (
          <div className="flex items-center gap-1.5">
            <button
              onClick={onExport}
              className="rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-all"
              style={{ color: "var(--color-text-muted)", borderColor: "rgba(148,163,184,0.24)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.color = "var(--color-text-secondary)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.color = "var(--color-text-muted)")
              }
              title="Sohbeti disa aktar"
            >
              Aktar
            </button>
            <button
              onClick={onClear}
              className="rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-all"
              style={{ color: "var(--color-text-muted)", borderColor: "rgba(148,163,184,0.24)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.color = "var(--color-text-secondary)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.color = "var(--color-text-muted)")
              }
            >
              Temizle
            </button>
          </div>
        )}
      </div>

    </div>
  );
}

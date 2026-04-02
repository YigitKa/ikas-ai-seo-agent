import type { ActiveSkillSummary, SkillDefinition } from '../../types';

interface ChatHeaderProps {
  displayProductName?: string;
  displayProductCategory?: string | null;
  displaySeoScore?: number | null;
  productDetailUrl?: string;
  availableSkills: SkillDefinition[];
  activeSkill: ActiveSkillSummary | null;
  skillLoading: boolean;
  onSkillSelect: (slug: string) => void;
  onSkillClear: () => void;
  hasMessages: boolean;
  onClear: () => void;
  onExport: () => void;
}

export function ChatHeader({
  displayProductName,
  displayProductCategory,
  displaySeoScore,
  productDetailUrl,
  availableSkills,
  activeSkill,
  skillLoading,
  onSkillSelect,
  onSkillClear,
  hasMessages,
  onClear,
  onExport,
}: ChatHeaderProps) {
  const explicitSkillSlug =
    activeSkill?.explicit_skill_slug
    ?? (activeSkill?.selection_mode === 'explicit' ? activeSkill.slug : '');
  const skillValue = explicitSkillSlug ?? "";
  const skillHelperText = activeSkill
    ? [
        activeSkill.description && activeSkill.selection_mode === 'explicit'
          ? activeSkill.description
          : '',
        activeSkill.selection_mode === 'routed'
          ? `Otomatik secilen skill: ${activeSkill.name}`
          : activeSkill.selection_mode === 'default'
            ? `Varsayilan skill: ${activeSkill.name}`
            : activeSkill.selection_mode === 'merged'
              ? `Birlesik runtime: ${(activeSkill.merged_skill_slugs ?? []).join(' + ') || activeSkill.name}`
              : activeSkill.name,
        (activeSkill.resolved_tools?.length ?? 0) > 0
          ? `${activeSkill.resolved_tools?.length ?? 0} aktif tool`
          : activeSkill.allowed_tools.length
            ? `${activeSkill.allowed_tools.length} tool siniri`
            : '',
      ].filter(Boolean).join(' | ')
    : 'Skill secilmezse standart chat promptu kullanilir.';

  return (
    <div className="px-4 py-3" style={{ borderBottom: "1px solid rgba(148,163,184,0.16)" }}>
      <div className="flex flex-wrap items-start justify-between gap-3">
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

        <div className="min-w-[240px] max-w-full space-y-2">
          <div>
            <div
              className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: "var(--color-text-muted)" }}
            >
              Aktif skill
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={skillValue}
                onChange={(event) => {
                  const nextSlug = event.target.value;
                  if (!nextSlug) {
                    onSkillClear();
                    return;
                  }
                  onSkillSelect(nextSlug);
                }}
                disabled={skillLoading}
                className="min-w-[220px] rounded-lg px-3 py-2 text-[12px] outline-none disabled:opacity-50"
                style={{
                  background: 'rgba(15,23,42,0.78)',
                  border: '1px solid rgba(148,163,184,0.24)',
                  color: 'var(--color-text-primary)',
                }}
              >
                <option value="">Varsayilan sohbet</option>
                {availableSkills.map((skill) => (
                  <option key={skill.slug} value={skill.slug}>
                    {skill.name}
                  </option>
                ))}
              </select>
              {explicitSkillSlug && (
                <button
                  onClick={onSkillClear}
                  className="rounded-lg border px-2.5 py-2 text-[11px] font-medium transition-all"
                  style={{ color: "#cbd5f5", borderColor: "rgba(99,102,241,0.35)" }}
                >
                  Kaldir
                </button>
              )}
              {hasMessages && (
                <>
                  <button
                    onClick={onExport}
                    className="rounded-lg border px-2.5 py-2 text-[11px] font-medium transition-all"
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
                    className="rounded-lg border px-2.5 py-2 text-[11px] font-medium transition-all"
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
                </>
              )}
            </div>
            <div
              className="mt-1.5 max-w-[420px] text-[11px] leading-relaxed"
              style={{ color: activeSkill ? "#c7d2fe" : "var(--color-text-muted)" }}
            >
              {skillLoading && !availableSkills.length ? "Skill listesi yukleniyor..." : skillHelperText}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}

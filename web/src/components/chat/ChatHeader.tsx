import type { ActiveSkillSummary, SkillDefinition } from '../../types';

interface ChatHeaderProps {
  displayProductName?: string;
  displayProductCategory?: string | null;
  displaySeoScore?: number | null;
  productDetailUrl?: string;
  chatScope?: 'product' | 'store';
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
  chatScope,
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
  const skillValue = explicitSkillSlug ?? '';
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
    <div
      className="px-4 py-3"
      style={{
        borderBottom: '1px solid var(--chat-section-border)',
        background: 'linear-gradient(180deg, var(--chat-soft-card-bg), transparent)',
      }}
    >
      <div className="flex flex-col gap-2.5 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span
              className="rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]"
              style={{
                background: chatScope === 'store'
                  ? 'var(--chat-bubble-user-bg)'
                  : displayProductName ? 'var(--tint-info-soft)' : 'var(--chat-muted-card-bg)',
                border: chatScope === 'store'
                  ? '1px solid var(--chat-bubble-user-border)'
                  : displayProductName
                    ? '1px solid var(--color-border-info)'
                    : '1px solid var(--chat-section-border)',
                color: chatScope === 'store'
                  ? 'var(--color-text-brand-soft)'
                  : displayProductName ? 'var(--color-text-info)' : 'var(--color-text-secondary)',
              }}
            >
              {chatScope === 'store' ? 'Magaza Asistani' : displayProductName ? 'Aktif urun' : 'Sohbet'}
            </span>

            <div
              className="min-w-0 truncate text-[16px] font-semibold"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {chatScope === 'store'
                ? 'Magazanizi yonetin'
                : displayProductName || 'Bir urun secin veya sohbete baslayin'}
            </div>

            {displayProductName && productDetailUrl ? (
              <a
                href={productDetailUrl}
                target="_blank"
                rel="noreferrer"
                className="flex-shrink-0 rounded-md px-2 py-1 text-[10px] font-medium transition-opacity hover:opacity-80"
                style={{
                  background: 'var(--chat-bubble-user-bg)',
                  color: 'var(--color-text-brand-soft)',
                  border: '1px solid var(--chat-bubble-user-border)',
                }}
                title="ikas urun detayina git"
              >
                ikas link
              </a>
            ) : null}
          </div>

          <div
            className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {chatScope === 'store' ? (
              <span>Siparisler, stok, musteriler ve daha fazlasi</span>
            ) : (
              <>
                <span>{displayProductCategory || 'Kategori yok'}</span>
                {typeof displaySeoScore === 'number' ? <span>SEO {displaySeoScore}/100</span> : null}
              </>
            )}
          </div>
        </div>

        <div className="flex min-w-0 flex-wrap items-center gap-2 xl:justify-end">
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
            className="min-w-[210px] max-w-full rounded-lg px-3 py-2 text-[12px] outline-none disabled:opacity-50"
            style={{
              background: 'var(--chat-input-bg)',
              border: '1px solid var(--chat-soft-card-border)',
              color: 'var(--color-text-primary)',
              boxShadow: 'var(--chat-soft-card-shadow)',
            }}
          >
            <option value="">Varsayilan sohbet</option>
            {availableSkills.map((skill) => (
              <option key={skill.slug} value={skill.slug}>
                {skill.name}
              </option>
            ))}
          </select>

          {explicitSkillSlug ? (
            <button
              onClick={onSkillClear}
              className="rounded-lg border px-2.5 py-2 text-[11px] font-medium transition-all hover:-translate-y-0.5"
              style={{
                color: 'var(--color-text-brand-soft)',
                borderColor: 'var(--chat-bubble-user-border)',
                background: 'var(--chat-bubble-user-bg)',
              }}
            >
              Kaldir
            </button>
          ) : null}

          {hasMessages ? (
            <>
              <button
                onClick={onExport}
                className="rounded-lg border px-2.5 py-2 text-[11px] font-medium transition-all hover:-translate-y-0.5"
                style={{
                  color: 'var(--color-text-secondary)',
                  borderColor: 'var(--chat-soft-card-border)',
                  background: 'var(--chat-muted-card-bg)',
                }}
                title="Sohbeti disa aktar"
              >
                Aktar
              </button>
              <button
                onClick={onClear}
                className="rounded-lg border px-2.5 py-2 text-[11px] font-medium transition-all hover:-translate-y-0.5"
                style={{
                  color: 'var(--color-text-secondary)',
                  borderColor: 'var(--chat-soft-card-border)',
                  background: 'var(--chat-muted-card-bg)',
                }}
              >
                Temizle
              </button>
            </>
          ) : null}
        </div>
      </div>

      <div
        className="mt-2 truncate text-[11px]"
        style={{ color: activeSkill ? 'var(--color-text-brand-soft)' : 'var(--color-text-muted)' }}
      >
        {skillLoading && !availableSkills.length ? 'Skill listesi yukleniyor...' : skillHelperText}
      </div>
    </div>
  );
}

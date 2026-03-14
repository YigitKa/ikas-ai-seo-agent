import { memo } from 'react';
import { getSuggestionCardPalette, type SuggestionOption } from '../suggestionUtils';
import MarkdownMessage from './MarkdownMessage';

function SuggestionCards({
  options,
  onApplyOption,
  disabled,
}: {
  options: SuggestionOption[];
  onApplyOption: (option: SuggestionOption, index: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="mt-4 flex flex-wrap gap-3">
      {options.map((option, index) => {
        const palette = getSuggestionCardPalette(option.tone, index);

        return (
          <div
            key={`${option.tone}-${index}`}
            className="relative flex min-w-[220px] flex-1 flex-col overflow-hidden rounded-2xl p-4 transition-all duration-200 hover:-translate-y-0.5"
            style={{
              background: palette.background,
              border: `1px solid ${palette.border}`,
              boxShadow: palette.shadow,
            }}
          >
            <div
              className="absolute inset-x-0 top-0 h-1"
              style={{ background: `linear-gradient(90deg, ${palette.accent}, transparent)` }}
            />
            <div className="flex items-center justify-between gap-3">
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]"
                style={{ background: palette.badgeBackground, color: palette.badgeColor }}
              >
                {option.tone}
              </span>
              <span className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                Secenek {index + 1}
              </span>
            </div>

            <div className="mt-3 flex-1 text-sm leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>
              <MarkdownMessage content={option.value} />
            </div>

            <button
              type="button"
              onClick={() => onApplyOption(option, index)}
              disabled={disabled}
              className="mt-4 rounded-xl px-3 py-2 text-xs font-semibold transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50"
              style={{
                background: palette.buttonBackground,
                border: `1px solid ${palette.buttonBorder}`,
                color: palette.buttonColor,
              }}
            >
              Bunu Uygula
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default memo(SuggestionCards, (prev, next) =>
  prev.options.length === next.options.length &&
  prev.disabled === next.disabled,
);

import { useEffect, useRef, useState } from 'react';
import type { PromptParamOption, ParamTriggerState } from './promptParams';
import {
  buildPromptParamOptions,
  getParamTriggerState,
  resolvePromptTemplate,
} from './promptParams';
import { ChatStatusDeck, type ChatStatusItem } from './ChatStatusDeck';
import type { Product, SeoScore } from '../../types';

interface ChatInputProps {
  product?: Product | null;
  score?: SeoScore | null;
  productId?: string;
  displayProductName?: string;
  isLoading: boolean;
  isAutoIntroActive: boolean;
  sessionStatusItems: ChatStatusItem[];
  onSend: (text: string) => void;
  onCancel: () => void;
}

export function ChatInput({
  product,
  score,
  productId,
  displayProductName,
  isLoading,
  isAutoIntroActive,
  sessionStatusItems,
  onSend,
  onCancel,
}: ChatInputProps) {
  const [input, setInput] = useState('');
  const [paramTrigger, setParamTrigger] = useState<ParamTriggerState | null>(null);
  const [activeParamIndex, setActiveParamIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const promptParamOptions = buildPromptParamOptions(product, score);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = '0px';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
  }, [input]);

  useEffect(() => {
    setInput('');
    setParamTrigger(null);
    setActiveParamIndex(0);
  }, [productId]);

  const syncParamTrigger = (value: string, caretPosition: number | null) => {
    setParamTrigger(getParamTriggerState(value, caretPosition));
    setActiveParamIndex(0);
  };

  const applyParamOption = (option: PromptParamOption) => {
    if (!paramTrigger) return;
    const closingIndex = input.indexOf('}', paramTrigger.start);
    const replaceEnd =
      closingIndex !== -1 && closingIndex >= paramTrigger.end
        ? closingIndex + 1
        : paramTrigger.end;
    const nextValue = `${input.slice(0, paramTrigger.start)}${option.value}${input.slice(replaceEnd)}`;
    const nextCaretPosition = paramTrigger.start + option.value.length;
    setInput(nextValue);
    setParamTrigger(null);
    setActiveParamIndex(0);
    window.requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      textarea.focus();
      textarea.setSelectionRange(nextCaretPosition, nextCaretPosition);
    });
  };

  const submitPrompt = (text: string) => {
    const value = resolvePromptTemplate(text, promptParamOptions).trim();
    if (!value) return;
    onSend(value);
    setInput('');
    setParamTrigger(null);
    setActiveParamIndex(0);
  };

  const handleSend = () => submitPrompt(input);

  const filteredParamOptions = paramTrigger
    ? promptParamOptions.filter(
        (option) =>
          !paramTrigger.query ||
          option.searchText.includes(paramTrigger.query.toLowerCase()) ||
          option.key.toLowerCase().includes(paramTrigger.query.toLowerCase()),
      )
    : [];
  const visibleParamOptions = filteredParamOptions.slice(0, 8);
  const showParamMenu = !isAutoIntroActive && visibleParamOptions.length > 0;
  const footerHint = isAutoIntroActive
    ? 'Ilk proaktif SEO analizi hazirlaniyor.'
    : '{} ile hazir urun alanlarini mesaja ekleyebilirsin.';

  return (
    <div className="px-4 py-3" style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
      <div
        className="flex items-end gap-2 rounded-[20px] border px-2.5 py-2"
        style={{
          borderColor: 'var(--color-border-subtle)',
          background: 'var(--surface-raised)',
        }}
      >
        <div className="relative flex-1">
          {showParamMenu ? (
            <div
              className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl"
              style={{
                background: 'var(--surface-code)',
                border: '1px solid var(--color-border-primary)',
                boxShadow: '0 14px 40px rgba(0, 0, 0, 0.34)',
              }}
            >
              <div
                className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em]"
                style={{
                  color: 'var(--color-text-muted)',
                  borderBottom: '1px solid var(--alpha-white-6)',
                }}
              >
                Parametreler
              </div>
              <div className="max-h-64 overflow-y-auto p-1.5">
                {visibleParamOptions.map((option, index) => (
                  <button
                    key={option.key}
                    type="button"
                    onMouseDown={(event) => {
                      event.preventDefault();
                      applyParamOption(option);
                    }}
                    className="mb-1 block w-full rounded-lg px-2.5 py-2 text-left last:mb-0"
                    style={{
                      background:
                        index === activeParamIndex
                          ? 'var(--tint-primary-soft)'
                          : 'var(--alpha-white-3)',
                      border:
                        index === activeParamIndex
                          ? '1px solid var(--color-border-primary)'
                          : '1px solid transparent',
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px]" style={{ color: 'var(--color-text-brand-soft)' }}>
                        {`{${option.key}}`}
                      </span>
                      <span className="text-[11px] font-medium text-white">
                        {option.label}
                      </span>
                    </div>
                    <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                      {option.description}
                    </div>
                    <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                      {option.preview}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <textarea
            ref={textareaRef}
            value={input}
            disabled={isAutoIntroActive}
            rows={1}
            onChange={(event) => {
              const nextValue = event.target.value;
              setInput(nextValue);
              syncParamTrigger(nextValue, event.target.selectionStart);
            }}
            onSelect={(event) => {
              syncParamTrigger(
                event.currentTarget.value,
                event.currentTarget.selectionStart,
              );
            }}
            onKeyDown={(event) => {
              if (showParamMenu) {
                if (event.key === 'ArrowDown') {
                  event.preventDefault();
                  setActiveParamIndex((prev) => (prev + 1) % visibleParamOptions.length);
                  return;
                }
                if (event.key === 'ArrowUp') {
                  event.preventDefault();
                  setActiveParamIndex((prev) =>
                    prev === 0 ? visibleParamOptions.length - 1 : prev - 1,
                  );
                  return;
                }
                if ((event.key === 'Enter' || event.key === 'Tab') && visibleParamOptions[activeParamIndex]) {
                  event.preventDefault();
                  applyParamOption(visibleParamOptions[activeParamIndex]);
                  return;
                }
                if (event.key === 'Escape') {
                  event.preventDefault();
                  setParamTrigger(null);
                  return;
                }
              }

              if (event.key === 'Enter' && !event.shiftKey && !isLoading) {
                event.preventDefault();
                handleSend();
              }
            }}
            placeholder={
              isAutoIntroActive
                ? 'Asistan urunu inceliyor...'
                : displayProductName
                  ? `${displayProductName} icin mesaj yaz... { ile alan ekle`
                  : 'Mesaj yaz... { ile alan ekle.'
            }
            className="min-h-[42px] w-full resize-none rounded-2xl px-3 py-2 text-[13px] outline-none transition-all"
            style={{
              background: 'var(--surface-panel)',
              border: '1px solid var(--color-border-subtle)',
              color: 'var(--color-text-primary)',
              opacity: isAutoIntroActive ? 0.7 : 1,
              cursor: isAutoIntroActive ? 'not-allowed' : 'text',
            }}
            onFocus={(event) => (event.currentTarget.style.borderColor = 'rgba(99,102,241,0.7)')}
            onBlur={(event) => {
              event.currentTarget.style.borderColor = 'var(--color-border-subtle)';
              setParamTrigger(null);
            }}
          />
        </div>

        <button
          onClick={isLoading ? onCancel : handleSend}
          disabled={(!isLoading && !input.trim()) || (isAutoIntroActive && !isLoading)}
          className={`flex min-h-[42px] flex-shrink-0 items-center justify-center rounded-xl px-3 text-white transition-all hover:opacity-90 disabled:opacity-30 ${isLoading ? 'min-w-[62px]' : 'w-10'}`}
          style={{
            background: isLoading
              ? 'linear-gradient(135deg, var(--color-danger), var(--color-orange))'
              : 'linear-gradient(135deg, var(--color-primary), var(--color-primary))',
          }}
          title={isLoading ? 'Aktif istegi durdur' : 'Mesaji gonder'}
        >
          {isLoading ? (
            <span className="text-[11px] font-semibold uppercase tracking-[0.12em]">
              Stop
            </span>
          ) : (
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          )}
        </button>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-1">
        <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          {footerHint}
        </div>
        <div className="min-w-0 flex-1">
          <ChatStatusDeck items={sessionStatusItems} />
        </div>
      </div>
    </div>
  );
}

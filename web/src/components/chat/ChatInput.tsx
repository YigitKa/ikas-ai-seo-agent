import { useEffect, useRef, useState } from "react";
import type { PromptParamOption, ParamTriggerState } from "./promptParams";
import {
  buildPromptParamOptions,
  getParamTriggerState,
  resolvePromptTemplate,
} from "./promptParams";
import { ChatStatusDeck, type ChatStatusItem } from "./ChatStatusDeck";
import type { Product, SeoScore } from "../../types";

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
  const [input, setInput] = useState("");
  const [paramTrigger, setParamTrigger] = useState<ParamTriggerState | null>(
    null,
  );
  const [activeParamIndex, setActiveParamIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const promptParamOptions = buildPromptParamOptions(product, score);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
  }, [input]);

  // Reset input when product changes
  useEffect(() => {
    setInput("");
    setParamTrigger(null);
    setActiveParamIndex(0);
  }, [productId]);

  const syncParamTrigger = (value: string, caretPosition: number | null) => {
    setParamTrigger(getParamTriggerState(value, caretPosition));
    setActiveParamIndex(0);
  };

  const applyParamOption = (option: PromptParamOption) => {
    if (!paramTrigger) return;
    const closingIndex = input.indexOf("}", paramTrigger.start);
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
    setInput("");
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
  const showParamMenu = !isAutoIntroActive && filteredParamOptions.length > 0;

  return (
    <div className="p-3" style={{ borderTop: "1px solid rgba(148,163,184,0.16)" }}>
      <div className="flex items-end gap-2 rounded-2xl border p-2" style={{ borderColor: "rgba(148,163,184,0.2)", background: "rgba(15,23,42,0.66)" }}>
        <div className="relative flex-1">
          {showParamMenu && (
            <div
              className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl"
              style={{
                background: "rgba(15, 23, 42, 0.98)",
                border: "1px solid rgba(99, 102, 241, 0.22)",
                boxShadow: "0 14px 40px rgba(0, 0, 0, 0.34)",
              }}
            >
              <div
                className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em]"
                style={{
                  color: "var(--color-text-muted)",
                  borderBottom: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                Parametreler
              </div>
              <div className="max-h-64 overflow-y-auto p-1.5">
                {filteredParamOptions.slice(0, 8).map((option, index) => (
                  <button
                    key={option.key}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      applyParamOption(option);
                    }}
                    className="mb-1 block w-full rounded-lg px-2.5 py-2 text-left last:mb-0"
                    style={{
                      background:
                        index === activeParamIndex
                          ? "rgba(99, 102, 241, 0.14)"
                          : "rgba(255,255,255,0.02)",
                      border:
                        index === activeParamIndex
                          ? "1px solid rgba(99, 102, 241, 0.28)"
                          : "1px solid transparent",
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="font-mono text-[11px]"
                        style={{ color: "#c7d2fe" }}
                      >
                        {`{${option.key}}`}
                      </span>
                      <span className="text-[11px] font-medium text-white">
                        {option.label}
                      </span>
                    </div>
                    <div
                      className="mt-1 text-[11px]"
                      style={{ color: "var(--color-text-secondary)" }}
                    >
                      {option.description}
                    </div>
                    <div
                      className="mt-1 text-[11px]"
                      style={{ color: "var(--color-text-muted)" }}
                    >
                      {option.preview}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            disabled={isAutoIntroActive}
            rows={1}
            onChange={(e) => {
              const nextValue = e.target.value;
              setInput(nextValue);
              syncParamTrigger(nextValue, e.target.selectionStart);
            }}
            onSelect={(e) => {
              syncParamTrigger(
                e.currentTarget.value,
                e.currentTarget.selectionStart,
              );
            }}
            onKeyDown={(e) => {
              if (showParamMenu) {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setActiveParamIndex(
                    (prev) =>
                      (prev + 1) % filteredParamOptions.slice(0, 8).length,
                  );
                  return;
                }
                if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setActiveParamIndex((prev) =>
                    prev === 0
                      ? filteredParamOptions.slice(0, 8).length - 1
                      : prev - 1,
                  );
                  return;
                }
                if (
                  (e.key === "Enter" || e.key === "Tab") &&
                  filteredParamOptions[activeParamIndex]
                ) {
                  e.preventDefault();
                  applyParamOption(filteredParamOptions[activeParamIndex]);
                  return;
                }
                if (e.key === "Escape") {
                  e.preventDefault();
                  setParamTrigger(null);
                  return;
                }
              }

              if (e.key === "Enter" && !e.shiftKey && !isLoading) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={
              isAutoIntroActive
                ? "Asistan urunu inceliyor..."
                : displayProductName
                  ? `${displayProductName} icin soru sorun. { ile hazir alan ekleyin...`
                  : "Mesaj yazin... { ile parametre ekleyin."
            }
            className="min-h-[44px] w-full resize-none rounded-xl px-3 py-2 text-[13px] outline-none transition-all"
            style={{
              background: "rgba(15,23,42,0.86)",
              border: "1px solid rgba(148,163,184,0.2)",
              color: "var(--color-text-primary)",
              opacity: isAutoIntroActive ? 0.7 : 1,
              cursor: isAutoIntroActive ? "not-allowed" : "text",
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(99,102,241,0.7)")}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "rgba(148,163,184,0.2)";
              setParamTrigger(null);
            }}
          />
          <div
            className="mt-1 px-1 text-[11px]"
            style={{ color: "var(--color-text-muted)" }}
          >
            {isAutoIntroActive
              ? "Ilk proaktif SEO analizi hazirlaniyor."
              : <>
                  {"{}"} ile `productDescription`, `productMetaTitle` veya
                  `seoMetricsSummary` gibi alanlari hizlica ekle.
                </>
            }
          </div>
        </div>

        <button
          onClick={
            isLoading
              ? onCancel
              : handleSend
          }
          disabled={
            (!isLoading && !input.trim()) ||
            (isAutoIntroActive && !isLoading)
          }
          className={`flex min-h-[44px] flex-shrink-0 items-center justify-center rounded-xl px-3 text-white transition-all hover:opacity-90 disabled:opacity-30 ${isLoading ? "min-w-[64px]" : "w-11"}`}
          style={{
            background: isLoading
              ? "linear-gradient(135deg, #ef4444, #f97316)"
              : "linear-gradient(135deg, #6366f1, #8b5cf6)",
          }}
          title={isLoading ? "Aktif istegi durdur" : "Mesaji gonder"}
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
      <div className="mt-1.5 px-1">
        <ChatStatusDeck items={sessionStatusItems} />
      </div>
    </div>
  );
}

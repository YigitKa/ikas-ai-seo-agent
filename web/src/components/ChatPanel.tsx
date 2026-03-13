import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getLmStudioLiveStatus, getSettings } from "../api/client";
import { useChat } from "../hooks/useChat";
import type { Product, SeoScore, SeoSuggestion } from "../types";
import {
  formatCompactNumber,
  formatDuration,
  readMetaNumber,
} from "./chat/chatUtils";
import { MessageBubble, type SuggestionOption } from "./chat/ChatMessage";
import SeoScoreChatMessage from "./chat/SeoScoreChatMessage";
import SuggestionDiffModal from "./chat/SuggestionDiffModal";
import {
  ChatStatusDeck,
  ReconnectingBanner,
  StarterStateCard,
  type ChatStatusItem,
} from "./chat/ChatPanelUi";
import { STARTER_PROMPTS } from "./chat/chatPanelConstants";
import {
  buildPromptParamOptions,
  getParamTriggerState,
  resolvePromptTemplate,
  type ParamTriggerState,
} from "./chat/promptParams";

interface Props {
  productId?: string;
  productName?: string;
  productCategory?: string | null;
  seoScore?: number | null;
  product?: Product | null;
  score?: SeoScore | null;
  productDetailUrl?: string;
}

// ── ChatPanel ─────────────────────────────────────────────────────────────────

export default function ChatPanel({
  productId,
  productName,
  productCategory,
  seoScore,
  product,
  score,
  productDetailUrl,
}: Props) {
  const settingsQ = useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
    staleTime: 5 * 60 * 1000,
  });
  const configuredModel = settingsQ.data?.ai_model_name?.trim();
  const configuredProvider = settingsQ.data?.ai_provider?.trim();
  const lmStatusQ = useQuery({
    queryKey: ["lm-studio-live-status"],
    queryFn: () => getLmStudioLiveStatus(),
    enabled: configuredProvider === "lm-studio",
    staleTime: 2_000,
    refetchInterval: configuredProvider === "lm-studio" ? 5_000 : false,
  });

  const configuredAssistantLabel =
    configuredModel || configuredProvider || "AI modeli";
  const displayProductName = productName || product?.name;
  const displayProductCategory = productCategory ?? product?.category ?? null;
  const displaySeoScore = seoScore ?? score?.total_score ?? null;

  const {
    messages,
    isLoading,
    isReconnecting,
    isAutoIntroActive,
    pendingSince,
    liveChunkCount,
    liveTokenEstimate,
    pendingSuggestion,
    mcpState,
    sendMessage,
    addLocalMessage,
    cancelMessage,
    clearHistory,
    connect,
    disconnect,
  } = useChat({
    id: productId,
    name: displayProductName,
    category: displayProductCategory,
    score: displaySeoScore,
    assistantLabel: configuredAssistantLabel,
  });

  const [input, setInput] = useState("");
  const [liveElapsedSeconds, setLiveElapsedSeconds] = useState(0);
  const [paramTrigger, setParamTrigger] = useState<ParamTriggerState | null>(
    null,
  );
  const [activeParamIndex, setActiveParamIndex] = useState(0);
  const [diffModalSuggestion, setDiffModalSuggestion] = useState<SeoSuggestion | null>(null);
  const [diffModalAction, setDiffModalAction] = useState<string>("");
  const prevPendingSuggestionRef = useRef<SeoSuggestion | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const promptParamOptions = buildPromptParamOptions(product, score);

  // Connect/disconnect WebSocket on mount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // Live elapsed timer while request is pending
  useEffect(() => {
    if (pendingSince === null) {
      setLiveElapsedSeconds(0);
      return;
    }
    const updateElapsed = () =>
      setLiveElapsedSeconds((performance.now() - pendingSince) / 1000);
    updateElapsed();
    const intervalId = window.setInterval(updateElapsed, 100);
    return () => window.clearInterval(intervalId);
  }, [pendingSince]);

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

  // Derived state
  const latestAssistant = [...messages]
    .reverse()
    .find(
      (msg) => msg.role === "assistant" && typeof msg.meta?.model === "string",
    );
  const liveContextLength =
    lmStatusQ.data?.selected_model?.context_length ?? null;
  let sessionTotalTokens = 0;
  for (const msg of messages) {
    if (msg.role !== "assistant") continue;
    const totalTokens = readMetaNumber(msg.meta, "total_tokens");
    const inputTokens = readMetaNumber(msg.meta, "input_tokens");
    const outputTokens = readMetaNumber(msg.meta, "output_tokens");
    sessionTotalTokens +=
      totalTokens ?? (inputTokens ?? 0) + (outputTokens ?? 0);
  }
  const assistantLabel =
    typeof latestAssistant?.meta?.model === "string"
      ? String(latestAssistant.meta.model)
      : configuredAssistantLabel;
  const mcpStatusLabel = mcpState.initialized
    ? "bagli"
    : mcpState.hasToken
      ? "bekliyor"
      : "kapali";
  const mcpStatusTone: ChatStatusItem["tone"] = mcpState.initialized
    ? "success"
    : mcpState.hasToken
      ? "warn"
      : "neutral";
  const liveRateBase =
    liveTokenEstimate > 0 ? liveTokenEstimate : liveChunkCount;
  const liveTokensPerSecond =
    liveElapsedSeconds > 0 && liveRateBase > 0
      ? liveRateBase / liveElapsedSeconds
      : 0;
  const formattedLiveTokensPerSecond =
    liveTokensPerSecond >= 20
      ? liveTokensPerSecond.toFixed(0)
      : liveTokensPerSecond.toFixed(1);

  const isInspectingProduct = isAutoIntroActive && messages.length === 0;
  const showStarterState =
    !isAutoIntroActive &&
    (messages.length === 0 || messages.every((msg) => msg.role === "system"));
  const filteredParamOptions = paramTrigger
    ? promptParamOptions.filter(
        (option) =>
          !paramTrigger.query ||
          option.searchText.includes(paramTrigger.query.toLowerCase()) ||
          option.key.toLowerCase().includes(paramTrigger.query.toLowerCase()),
      )
    : [];
  const showParamMenu = !isAutoIntroActive && filteredParamOptions.length > 0;
  const sessionStatusItems: ChatStatusItem[] = [
    { label: "Model", value: assistantLabel, tone: "neutral" },
    { label: "MCP", value: mcpStatusLabel, tone: mcpStatusTone },
  ];

  if (mcpState.initialized) {
    sessionStatusItems.push({
      label: "Arac",
      value: String(mcpState.toolCount),
      tone: "success",
    });
  }

  if (sessionTotalTokens > 0) {
    sessionStatusItems.push({
      label: "Token",
      value: `${formatCompactNumber(sessionTotalTokens)} tok`,
      tone: "neutral",
    });
  }

  if (typeof liveContextLength === "number" && liveContextLength > 0) {
    sessionStatusItems.push({
      label: "Context",
      value: formatCompactNumber(liveContextLength),
      tone: "neutral",
    });
  }

  if (isLoading) {
    sessionStatusItems.push({
      label: "Sure",
      value: formatDuration(liveElapsedSeconds),
      tone: "warn",
    });
  }

  if (isLoading && liveElapsedSeconds > 0 && liveRateBase > 0) {
    sessionStatusItems.push({
      label: "Canli Hiz",
      value: `${formattedLiveTokensPerSecond} tok/sn`,
      tone: "success",
    });
  }

  // Handlers
  const syncParamTrigger = (value: string, caretPosition: number | null) => {
    setParamTrigger(getParamTriggerState(value, caretPosition));
    setActiveParamIndex(0);
  };

  const applyParamOption = (option: (typeof promptParamOptions)[number]) => {
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
    sendMessage(value);
    setInput("");
    setParamTrigger(null);
    setActiveParamIndex(0);
  };

  const handleSend = () => submitPrompt(input);
  const handleStarterPrompt = (prompt: (typeof STARTER_PROMPTS)[number]) =>
    submitPrompt(prompt.template);
  const ACTION_LABELS: Record<string, string> = {
    single_apply_meta: "\u{1F527} Meta alanlarini duzelt",
    single_apply_content: "\u{1F4DD} Icerik alanlarini duzelt",
    single_apply_all: "\u{1F680} Tum alanlari duzelt",
    single_apply_cancel: "\u{274C} Iptal",
    single_apply_confirm: "\u{2705} Onayla",
  };

  const handleApplySuggestionOption = (
    option: SuggestionOption,
    index: number,
  ) => {
    if (option.action) {
      const label = ACTION_LABELS[option.action] || option.value;
      addLocalMessage({ role: "user", content: label });
      sendMessage(`[[CHAT_ACTION:${option.action}]]`, { hidden: true });
      return;
    }
    const label = `${index + 1}. secenegi sec: ${option.tone}`;
    addLocalMessage({ role: "user", content: label });
    sendMessage(
      `${index + 1}. secenegi sectim.\nTon: ${option.tone}\nIcerik: ${option.value}\nBu secenek dogrultusunda urun icin somut SEO degerleri olustur ve save_seo_suggestion araci ile kaydet.`,
      { hidden: true },
    );
  };

  // Open diff modal when backend returns a pending suggestion for review
  const openDiffModalForAction = useCallback(
    (suggestion: SeoSuggestion, action: string) => {
      setDiffModalSuggestion(suggestion);
      setDiffModalAction(action);
    },
    [],
  );

  // When pendingSuggestion changes (from backend response), open the diff modal
  useEffect(() => {
    if (
      pendingSuggestion &&
      pendingSuggestion !== prevPendingSuggestionRef.current &&
      pendingSuggestion.status === "pending_review"
    ) {
      openDiffModalForAction(pendingSuggestion, diffModalAction || "single_apply_all");
    }
    prevPendingSuggestionRef.current = pendingSuggestion;
  }, [pendingSuggestion, openDiffModalForAction, diffModalAction]);

  const handleDiffApprove = (editedSuggestion: SeoSuggestion) => {
    setDiffModalSuggestion(null);
    // Send edited values back for apply
    const payload = JSON.stringify({
      action: diffModalAction,
      edits: {
        suggested_name: editedSuggestion.suggested_name,
        suggested_meta_title: editedSuggestion.suggested_meta_title,
        suggested_meta_description: editedSuggestion.suggested_meta_description,
        suggested_description: editedSuggestion.suggested_description,
        suggested_description_en: editedSuggestion.suggested_description_en,
      },
    });
    addLocalMessage({ role: "user", content: "\u{2705} Degisiklikleri onayliyorum" });
    sendMessage(`[[CHAT_ACTION:single_apply_execute:${payload}]]`, { hidden: true });
  };

  const handleDiffReject = () => {
    setDiffModalSuggestion(null);
    addLocalMessage({ role: "user", content: "\u{274C} Iptal ettim" });
    sendMessage("[[CHAT_ACTION:single_apply_cancel]]", { hidden: true });
  };



  return (
    <div
      className="flex h-full flex-col overflow-hidden rounded-2xl"
      style={{
        background:
          "radial-gradient(circle at top left, rgba(99,102,241,0.12), transparent 28%), linear-gradient(180deg, rgba(15,23,42,0.96), rgba(10,14,27,0.98))",
        border: "1px solid rgba(148,163,184,0.18)",
        boxShadow: "0 22px 48px rgba(2, 6, 23, 0.5)",
      }}
    >
      {/* ── Header ── */}
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

          {messages.length > 0 && (
            <button
              onClick={clearHistory}
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
          )}
        </div>

      </div>

      {/* ── Reconnecting banner ── */}
      {isReconnecting && <ReconnectingBanner />}

      {/* ── Messages ── */}
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-4">
        {/* Score analysis — shown as the app's first message before LLM */}
        {score && productId && (
          <SeoScoreChatMessage key={`score-${productId}`} score={score} />
        )}

        {showStarterState && (
          <StarterStateCard
            prompts={STARTER_PROMPTS}
            onPromptClick={handleStarterPrompt}
            disabled={isLoading}
          />
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            msg={msg}
            assistantLabel={assistantLabel}
            fallbackContextLength={liveContextLength}
            onApplyOption={handleApplySuggestionOption}
            applyDisabled={isLoading}
          />
        ))}

        {(isLoading || isInspectingProduct) && (
          <div
            className="mr-6 rounded-2xl px-4 py-3"
            style={{
              background: "linear-gradient(180deg, rgba(30,41,59,0.75), rgba(15,23,42,0.8))",
              border: "1px solid rgba(148,163,184,0.2)",
            }}
          >
            <div className="flex items-center gap-2">
              <div className="flex gap-1">
                <span
                  className="typing-dot h-1.5 w-1.5 rounded-full"
                  style={{ background: "var(--color-primary-light)" }}
                />
                <span
                  className="typing-dot h-1.5 w-1.5 rounded-full"
                  style={{ background: "var(--color-primary-light)" }}
                />
                <span
                  className="typing-dot h-1.5 w-1.5 rounded-full"
                  style={{ background: "var(--color-primary-light)" }}
                />
              </div>
              <span
                className="text-xs"
                style={{ color: "var(--color-text-muted)" }}
              >
                {isAutoIntroActive
                  ? "Asistan urunu inceliyor..."
                  : `${assistantLabel} dusunuyor...`}
              </span>
            </div>
            {isLoading && (
              <div
                className="mt-2 text-[11px]"
                style={{ color: "var(--color-text-secondary)" }}
              >
                Sure: {formatDuration(liveElapsedSeconds)}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Input ── */}
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
                ? cancelMessage
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

      {diffModalSuggestion && (
        <SuggestionDiffModal
          suggestion={diffModalSuggestion}
          product={product ?? undefined}
          onApprove={handleDiffApprove}
          onReject={handleDiffReject}
        />
      )}
    </div>
  );
}

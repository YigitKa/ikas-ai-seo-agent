import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getLmStudioLiveStatus, getSettings } from "../api/client";
import { useChat } from "../hooks/useChat";
import type { Product, SeoScore } from "../types";
import {
  formatCompactNumber,
  formatDuration,
  readMetaNumber,
} from "./chat/chatUtils";
import { MessageBubble, type SuggestionOption } from "./chat/ChatMessage";
import { extractSuggestionOptions } from "./chat/suggestionUtils";
import {
  buildPromptParamOptions,
  getParamTriggerState,
  resolvePromptTemplate,
  type ParamTriggerState,
  type StarterPrompt,
} from "./chat/promptParams";

interface Props {
  productId?: string;
  productName?: string;
  productCategory?: string | null;
  seoScore?: number | null;
  product?: Product | null;
  score?: SeoScore | null;
}

// ── StatusPill ────────────────────────────────────────────────────────────────

function StatusPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "neutral" | "success" | "warn";
}) {
  const palette = {
    neutral: {
      background: "rgba(148, 163, 184, 0.08)",
      color: "var(--color-text-secondary)",
      border: "1px solid rgba(148, 163, 184, 0.12)",
    },
    success: {
      background: "rgba(16, 185, 129, 0.10)",
      color: "#34d399",
      border: "1px solid rgba(16, 185, 129, 0.16)",
    },
    warn: {
      background: "rgba(245, 158, 11, 0.10)",
      color: "#fbbf24",
      border: "1px solid rgba(245, 158, 11, 0.16)",
    },
  } as const;

  return (
    <div
      className="rounded-full px-2 py-1 text-[10px] font-medium"
      style={palette[tone]}
      title={`${label}: ${value}`}
    >
      {label}: {value}
    </div>
  );
}

// ── ChatPanel ─────────────────────────────────────────────────────────────────

export default function ChatPanel({
  productId,
  productName,
  productCategory,
  seoScore,
  product,
  score,
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
    mcpState,
    sendMessage,
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
  const [interactionInput, setInteractionInput] = useState("");
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
    setInteractionInput("");
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

  const starterPrompts: StarterPrompt[] = [
    {
      label: "SEO metriklerini yorumla",
      template:
        "@local Bu mevcut SEO metriklerini alan bazinda yorumla ve sadece bu skorlara gore 3 oncelikli tavsiye ver.\n\n{seoMetricsSummary}",
    },
    {
      label: "Urun aciklamasini yorumla",
      template:
        "@local Bu urunun mevcut aciklamasini yorumla. Yalnizca eldeki metni kullan.\n\n{productDescription}",
    },
    {
      label: "Meta titlei yorumla",
      template:
        "@local Bu mevcut meta titlei SEO acisindan yorumla.\n\n{productMetaTitle}",
    },
    {
      label: "Meta descriptioni yorumla",
      template:
        "@local Bu mevcut meta descriptioni SEO acisindan yorumla.\n\n{productMetaDescription}",
    },
  ];

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
  const lastMessage = messages[messages.length - 1];
  const latestAssistantInteraction =
    lastMessage?.role === "assistant"
      ? extractSuggestionOptions(lastMessage.content)
      : { markdownContent: "", options: [] as SuggestionOption[] };
  const hasPendingInteraction =
    !isLoading && latestAssistantInteraction.options.length > 0;

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
  const handleStarterPrompt = (prompt: StarterPrompt) =>
    submitPrompt(prompt.template);
  const handleApplySuggestionOption = (
    option: SuggestionOption,
    index: number,
  ) => {
    if (option.action) {
      sendMessage(`[[CHAT_ACTION:${option.action}]]`, { hidden: true });
      return;
    }
    sendMessage(
      `${index + 1}. secenegi uygula.\nTon: ${option.tone}\nSecilen icerik: ${option.value}`,
      { hidden: true },
    );
  };

  const handleInteractionOptionSelect = (
    option: SuggestionOption,
    index: number,
  ) => {
    handleApplySuggestionOption(option, index);
    setInteractionInput("");
  };

  const handleInteractionSend = () => {
    const message = interactionInput.trim();
    if (!message) return;
    sendMessage(message);
    setInteractionInput("");
  };

  const handleInteractionSkip = () => {
    sendMessage(
      "Bu secenekleri simdilik pas geciyorum, baska bir yonden devam edelim.",
      { hidden: true },
    );
    setInteractionInput("");
  };

  return (
    <div
      className="flex h-full flex-col overflow-hidden rounded-xl"
      style={{
        background: "var(--color-bg-surface)",
        border: "1px solid var(--color-border)",
      }}
    >
      {/* ── Header ── */}
      <div
        className="px-4 py-3"
        style={{ borderBottom: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <div
                className="flex h-6 w-6 items-center justify-center rounded-md"
                style={{
                  background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                }}
              >
                <svg
                  className="h-3.5 w-3.5 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              </div>
              <span
                className="text-[13px] font-semibold"
                style={{ color: "var(--color-text-primary)" }}
              >
                AI Chat
              </span>
            </div>

            {displayProductName && (
              <div className="mt-2 min-w-0">
                <div className="truncate text-[18px] font-semibold text-white">
                  {displayProductName}
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
            )}
          </div>

          {messages.length > 0 && (
            <button
              onClick={clearHistory}
              className="text-[11px] font-medium transition-all"
              style={{ color: "var(--color-text-muted)" }}
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

        <div className="mt-3 flex flex-wrap gap-2">
          <StatusPill label="Model" value={assistantLabel} tone="neutral" />
          <StatusPill
            label="MCP"
            value={
              mcpState.initialized
                ? "bagli"
                : mcpState.hasToken
                  ? "bekliyor"
                  : "kapali"
            }
            tone={
              mcpState.initialized
                ? "success"
                : mcpState.hasToken
                  ? "warn"
                  : "neutral"
            }
          />
          {mcpState.initialized && (
            <StatusPill
              label="Arac"
              value={String(mcpState.toolCount)}
              tone="success"
            />
          )}
          {sessionTotalTokens > 0 && (
            <StatusPill
              label="Token"
              value={`${formatCompactNumber(sessionTotalTokens)} tok`}
              tone="neutral"
            />
          )}
          {typeof liveContextLength === "number" && liveContextLength > 0 && (
            <StatusPill
              label="Context"
              value={formatCompactNumber(liveContextLength)}
              tone="neutral"
            />
          )}
          {isLoading && (
            <StatusPill
              label="Sure"
              value={formatDuration(liveElapsedSeconds)}
              tone="warn"
            />
          )}
          {isLoading && liveElapsedSeconds > 0 && liveRateBase > 0 && (
            <StatusPill
              label="Canli Hiz"
              value={`${formattedLiveTokensPerSecond} tok/sn`}
              tone="success"
            />
          )}
        </div>
      </div>

      {/* ── Reconnecting banner ── */}
      {isReconnecting && (
        <div
          className="flex items-center gap-2 px-4 py-2 text-[12px] font-medium"
          style={{
            background: "rgba(245, 158, 11, 0.10)",
            borderBottom: "1px solid rgba(245, 158, 11, 0.20)",
            color: "#fbbf24",
          }}
        >
          <svg
            className="h-3.5 w-3.5 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          Yeniden bağlanılıyor...
        </div>
      )}

      {/* ── Messages ── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
        {showStarterState && (
          <div
            className="rounded-2xl p-4 text-center"
            style={{
              background:
                "linear-gradient(180deg, rgba(99, 102, 241, 0.10), rgba(17, 24, 39, 0.02))",
              border: "1px solid rgba(99, 102, 241, 0.15)",
            }}
          >
            <div
              className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl"
              style={{
                background: "rgba(99, 102, 241, 0.12)",
                color: "#c7d2fe",
              }}
            >
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.7}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <p
              className="mt-3 text-[13px] font-medium"
              style={{ color: "var(--color-text-primary)" }}
            >
              Secili urunun mevcut SEO metrikleri ve eldeki alanlariyla sohbet
              hazir.
            </p>
            <p
              className="mt-1 text-xs"
              style={{ color: "var(--color-text-muted)" }}
            >
              `@local` ile mevcut baglami yorumlat. {"{"} yazarak
              `productDescription` veya `seoMetricsSummary` gibi alanlari mesaja
              ekleyebilirsin.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {starterPrompts.map((prompt) => (
                <button
                  key={prompt.label}
                  onClick={() => handleStarterPrompt(prompt)}
                  disabled={isLoading}
                  className="rounded-full px-3 py-1.5 text-[11px] font-medium transition-all hover:opacity-90 disabled:opacity-40"
                  style={{
                    background: "rgba(99, 102, 241, 0.12)",
                    color: "#c7d2fe",
                    border: "1px solid rgba(99, 102, 241, 0.2)",
                  }}
                >
                  {prompt.label}
                </button>
              ))}
            </div>
          </div>
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
            className="mr-6 rounded-xl px-4 py-3"
            style={{
              background: "var(--color-bg-elevated)",
              border: "1px solid var(--color-border)",
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
      <div
        className="p-3"
        style={{ borderTop: "1px solid var(--color-border)" }}
      >
        <div className="flex items-end gap-2">
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

            {hasPendingInteraction && (
              <div
                className="mb-2 rounded-xl p-3"
                style={{
                  background:
                    "linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))",
                  border: "1px solid rgba(255,255,255,0.1)",
                }}
              >
                <p
                  className="text-[13px] font-semibold"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  {latestAssistantInteraction.markdownContent ||
                    "Bu adimda bir secim yapman gerekiyor. Hangi secenekle devam edelim?"}
                </p>
                <div className="mt-3 space-y-1.5">
                  {latestAssistantInteraction.options.map((option, index) => (
                    <button
                      key={`${option.tone}-${index}`}
                      type="button"
                      disabled={isLoading}
                      onClick={() =>
                        handleInteractionOptionSelect(option, index)
                      }
                      className="flex w-full items-start gap-3 rounded-lg px-3 py-2 text-left transition-all hover:opacity-95 disabled:opacity-50"
                      style={{
                        border: "1px solid rgba(255,255,255,0.1)",
                        background: "rgba(17, 24, 39, 0.5)",
                        color: "var(--color-text-primary)",
                      }}
                    >
                      <span className="mt-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-black/40 px-1.5 text-[10px] font-semibold">
                        {index + 1}
                      </span>
                      <span className="text-[12px]">{option.value}</span>
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={handleInteractionSkip}
                  disabled={isLoading}
                  className="mt-3 rounded-lg px-3 py-1.5 text-xs font-medium transition-all disabled:opacity-50"
                  style={{
                    border: "1px solid var(--color-border-light)",
                    color: "var(--color-text-secondary)",
                  }}
                >
                  Skip
                </button>
              </div>
            )}

            <textarea
              ref={textareaRef}
              value={hasPendingInteraction ? interactionInput : input}
              disabled={isAutoIntroActive}
              rows={1}
              onChange={(e) => {
                const nextValue = e.target.value;
                if (hasPendingInteraction) {
                  setInteractionInput(nextValue);
                  return;
                }
                setInput(nextValue);
                syncParamTrigger(nextValue, e.target.selectionStart);
              }}
              onSelect={(e) => {
                if (hasPendingInteraction) return;
                syncParamTrigger(
                  e.currentTarget.value,
                  e.currentTarget.selectionStart,
                );
              }}
              onKeyDown={(e) => {
                if (!hasPendingInteraction && showParamMenu) {
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
                    if (!hasPendingInteraction) {
                      setParamTrigger(null);
                    }
                    return;
                  }
                }

                if (e.key === "Enter" && !e.shiftKey && !isLoading) {
                  e.preventDefault();
                  if (hasPendingInteraction) {
                    handleInteractionSend();
                    return;
                  }
                  handleSend();
                }
              }}
              placeholder={
                isAutoIntroActive
                  ? "Asistan urunu inceliyor..."
                  : displayProductName
                    ? hasPendingInteraction
                      ? `${displayProductName} icin seceneklerden birini secin veya farkli talimat yazin...`
                      : `${displayProductName} icin soru sorun. { ile hazir alan ekleyin...`
                    : hasPendingInteraction
                      ? "Seceneklerden birini secin veya farkli talimat yazin..."
                      : "Mesaj yazin... { ile parametre ekleyin."
              }
              className="min-h-[44px] w-full resize-none rounded-lg px-3 py-2 text-[13px] outline-none transition-all"
              style={{
                background: "var(--color-bg-base)",
                border: "1px solid var(--color-border-light)",
                color: "var(--color-text-primary)",
                opacity: isAutoIntroActive ? 0.7 : 1,
                cursor: isAutoIntroActive ? "not-allowed" : "text",
              }}
              onFocus={(e) =>
                (e.currentTarget.style.borderColor = "var(--color-primary)")
              }
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "var(--color-border-light)";
                if (!hasPendingInteraction) {
                  setParamTrigger(null);
                }
              }}
            />
            <div
              className="mt-1 px-1 text-[11px]"
              style={{ color: "var(--color-text-muted)" }}
            >
              {isAutoIntroActive ? (
                "Ilk proaktif SEO analizi hazirlaniyor."
              ) : (
                <>
                  {hasPendingInteraction ? (
                    "Seceneklerden birine tiklayabilir veya metin kutusuna kendi yonlendirmeni yazabilirsin."
                  ) : (
                    <>
                      {"{"} ile `productDescription`, `productMetaTitle` veya
                      `seoMetricsSummary` gibi alanlari hizlica ekle.
                    </>
                  )}
                </>
              )}
            </div>
          </div>

          <button
            onClick={
              isLoading
                ? cancelMessage
                : hasPendingInteraction
                  ? handleInteractionSend
                  : handleSend
            }
            disabled={
              (!isLoading &&
                !(hasPendingInteraction
                  ? interactionInput.trim()
                  : input.trim())) ||
              (isAutoIntroActive && !isLoading)
            }
            className={`flex min-h-[44px] flex-shrink-0 items-center justify-center rounded-lg px-3 text-white transition-all hover:opacity-90 disabled:opacity-30 ${isLoading ? "min-w-[64px]" : "w-11"}`}
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
      </div>
    </div>
  );
}

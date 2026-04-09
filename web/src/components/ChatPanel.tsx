import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getLmStudioLiveStatus, getSettings, getSkills } from "../api/client";
import { useChat } from "../hooks/useChat";
import type { Product, SeoScore, SeoSuggestion, SkillDefinition } from "../types";
import {
  exportChatAsText,
  formatCompactNumber,
  formatDuration,
  readMetaNumber,
} from "./chat/chatUtils";
import type { SuggestionOption } from "./chat/ChatMessage";
import type { ChatStatusItem } from "./chat/ChatStatusDeck";
import SuggestionDiffModal from "./chat/SuggestionDiffModal";
import { ReconnectingBanner } from "./chat/ChatPanelUi";
import { STARTER_PROMPTS } from "./chat/chatPanelConstants";
import { resolvePromptTemplate, buildPromptParamOptions } from "./chat/promptParams";
import { ChatHeader } from "./chat/ChatHeader";
import { ChatMessages } from "./chat/ChatMessages";
import { ChatInput } from "./chat/ChatInput";

interface Props {
  productId?: string;
  productName?: string;
  productCategory?: string | null;
  seoScore?: number | null;
  product?: Product | null;
  score?: SeoScore | null;
  productDetailUrl?: string;
  requestedSkillSlug?: string;
  /** Override default starter prompts (e.g. store-level prompts on home page). */
  starterPrompts?: { label: string; template: string }[];
  /** Called whenever the chat loading state changes (e.g. for a parent switch-guard). */
  onLoadingChange?: (isLoading: boolean) => void;
}

const ACTION_LABELS: Record<string, string> = {
  single_apply_meta: "\u{1F527} Meta alanlarini duzelt",
  single_apply_content: "\u{1F4DD} Icerik alanlarini duzelt",
  single_apply_all: "\u{1F680} Tum alanlari duzelt",
  single_apply_cancel: "\u{274C} Iptal",
  single_apply_confirm: "\u{2705} Onayla",
};

export default function ChatPanel({
  productId,
  productName,
  productCategory,
  seoScore,
  product,
  score,
  productDetailUrl,
  requestedSkillSlug,
  starterPrompts: starterPromptsOverride,
  onLoadingChange,
}: Props) {
  const queryClient = useQueryClient();

  const handleProductUpdated = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["products"] });
    queryClient.invalidateQueries({ queryKey: ["product"] });
    queryClient.invalidateQueries({ queryKey: ["suggestions"] });
  }, [queryClient]);

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
    staleTime: 10_000,
    refetchInterval: configuredProvider === "lm-studio" ? 15_000 : false,
  });
  const skillsQ = useQuery({
    queryKey: ['skills'],
    queryFn: getSkills,
    staleTime: 60_000,
  });

  const configuredAssistantLabel = configuredModel || configuredProvider || "AI modeli";
  const displayProductName = productName || product?.name;
  const displayProductCategory = productCategory ?? product?.category ?? null;
  const displaySeoScore = seoScore ?? score?.total_score ?? null;

  const {
    messages, isLoading, isReconnecting, isAutoIntroActive, pendingSince,
    liveChunkCount, liveTokenEstimate, pendingSuggestion, activeSkill, mcpState,
    sendMessage, retryLastMessage, addLocalMessage, cancelMessage, clearHistory,
    setActiveSkill, clearActiveSkill, connect, disconnect,
  } = useChat({
    id: productId,
    name: displayProductName,
    category: displayProductCategory,
    score: displaySeoScore,
    assistantLabel: configuredAssistantLabel,
  }, handleProductUpdated);

  const [liveElapsedSeconds, setLiveElapsedSeconds] = useState(0);

  // Notify parent about loading state so it can guard against mid-stream product switches
  useEffect(() => {
    onLoadingChange?.(isLoading);
  }, [isLoading, onLoadingChange]);

  const [diffModalSuggestion, setDiffModalSuggestion] = useState<SeoSuggestion | null>(null);
  const [diffModalAction, setDiffModalAction] = useState<string>("");
  const prevPendingSuggestionRef = useRef<SeoSuggestion | null>(null);
  const requestedSkillRef = useRef<string>('');
  const promptParamOptions = buildPromptParamOptions(product, score);

  // Connect/disconnect WebSocket on mount
  useEffect(() => { connect(); return () => disconnect(); }, [connect, disconnect]);

  useEffect(() => {
    const normalized = requestedSkillSlug?.trim() || '';
    if (!normalized) {
      requestedSkillRef.current = '';
      return;
    }
    if (requestedSkillRef.current === normalized) {
      return;
    }
    requestedSkillRef.current = normalized;
    setActiveSkill(normalized);
  }, [requestedSkillSlug, setActiveSkill]);

  // Live elapsed timer while request is pending
  useEffect(() => {
    if (pendingSince === null) { setLiveElapsedSeconds(0); return; }
    const updateElapsed = () => setLiveElapsedSeconds((performance.now() - pendingSince) / 1000);
    updateElapsed();
    const intervalId = window.setInterval(updateElapsed, 100);
    return () => window.clearInterval(intervalId);
  }, [pendingSince]);

  // Derived state
  const latestAssistant = [...messages].reverse().find(
    (msg) => msg.role === "assistant" && typeof msg.meta?.model === "string",
  );
  const liveContextLength = lmStatusQ.data?.selected_model?.context_length ?? null;
  let sessionTotalTokens = 0;
  for (const msg of messages) {
    if (msg.role !== "assistant") continue;
    const totalTokens = readMetaNumber(msg.meta, "total_tokens");
    const inputTokens = readMetaNumber(msg.meta, "input_tokens");
    const outputTokens = readMetaNumber(msg.meta, "output_tokens");
    sessionTotalTokens += totalTokens ?? (inputTokens ?? 0) + (outputTokens ?? 0);
  }
  const assistantLabel = typeof latestAssistant?.meta?.model === "string"
    ? String(latestAssistant.meta.model) : configuredAssistantLabel;
  const mcpStatusLabel = mcpState.initialized ? "bagli" : mcpState.hasToken ? "bekliyor" : "kapali";
  const mcpStatusTone: ChatStatusItem["tone"] = mcpState.initialized ? "success" : mcpState.hasToken ? "warn" : "neutral";
  const liveRateBase = liveTokenEstimate > 0 ? liveTokenEstimate : liveChunkCount;
  const liveTokensPerSecond = liveElapsedSeconds > 0 && liveRateBase > 0 ? liveRateBase / liveElapsedSeconds : 0;
  const formattedLiveTokensPerSecond = liveTokensPerSecond >= 20 ? liveTokensPerSecond.toFixed(0) : liveTokensPerSecond.toFixed(1);

  const isInspectingProduct = isAutoIntroActive && messages.length === 0;
  const showStarterState = !isAutoIntroActive && (messages.length === 0 || messages.every((msg) => msg.role === "system"));
  const chatSkills = (skillsQ.data?.items ?? []).filter(
    (skill): skill is SkillDefinition => skill.status === 'active' && skill.applies_to.includes('chat'),
  );

  const sessionStatusItems: ChatStatusItem[] = [
    { label: "Model", value: assistantLabel, tone: "neutral" },
    { label: "MCP", value: mcpStatusLabel, tone: mcpStatusTone },
  ];
  if (activeSkill) {
    sessionStatusItems.push({ label: "Skill", value: activeSkill.name, tone: "success" });
  }
  if (mcpState.initialized) sessionStatusItems.push({ label: "Arac", value: String(mcpState.toolCount), tone: "success" });
  if (sessionTotalTokens > 0) sessionStatusItems.push({ label: "Token", value: `${formatCompactNumber(sessionTotalTokens)} tok`, tone: "neutral" });
  if (typeof liveContextLength === "number" && liveContextLength > 0) sessionStatusItems.push({ label: "Context", value: formatCompactNumber(liveContextLength), tone: "neutral" });
  if (isLoading) sessionStatusItems.push({ label: "Sure", value: formatDuration(liveElapsedSeconds), tone: "warn" });
  if (isLoading && liveElapsedSeconds > 0 && liveRateBase > 0) sessionStatusItems.push({ label: "Canli Hiz", value: `${formattedLiveTokensPerSecond} tok/sn`, tone: "success" });

  // Handlers
  const handleSend = useCallback((text: string) => {
    const value = resolvePromptTemplate(text, promptParamOptions).trim();
    if (!value) return;
    sendMessage(value);
  }, [promptParamOptions, sendMessage]);

  const handleStarterPrompt = useCallback((prompt: typeof STARTER_PROMPTS[number]) => {
    const value = resolvePromptTemplate(prompt.template, promptParamOptions).trim();
    if (!value) return;
    sendMessage(value);
  }, [promptParamOptions, sendMessage]);

  const handleApplySuggestionOption = useCallback((option: SuggestionOption, index: number) => {
    if (option.action) {
      const label = ACTION_LABELS[option.action] || option.value;
      addLocalMessage({ role: "user", content: label });
      sendMessage(`[[CHAT_ACTION:${option.action}]]`, { hidden: true });
      return;
    }
    const label = `${index + 1}. secenegi sec: ${option.tone}`;
    addLocalMessage({ role: "user", content: label });
    sendMessage(
      `[[GENERATE_SUGGESTION]]${index + 1}. secenegi sectim.\nTon: ${option.tone}\nIcerik: ${option.value}\nBu secenek dogrultusunda urun icin somut SEO degerleri olustur ve save_seo_suggestion araci ile kaydet.`,
      { hidden: true },
    );
  }, [addLocalMessage, sendMessage]);

  const openDiffModalForAction = useCallback(
    (suggestion: SeoSuggestion, action: string) => {
      setDiffModalSuggestion(suggestion);
      setDiffModalAction(action);
    },
    [],
  );

  useEffect(() => {
    if (pendingSuggestion && pendingSuggestion !== prevPendingSuggestionRef.current && pendingSuggestion.status === "pending_review") {
      openDiffModalForAction(pendingSuggestion, diffModalAction || "single_apply_all");
    }
    prevPendingSuggestionRef.current = pendingSuggestion;
  }, [pendingSuggestion, openDiffModalForAction, diffModalAction]);

  const handleDiffApprove = useCallback((editedSuggestion: SeoSuggestion) => {
    setDiffModalSuggestion(null);
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
  }, [addLocalMessage, diffModalAction, sendMessage]);

  const handleDiffReject = useCallback(() => {
    setDiffModalSuggestion(null);
    addLocalMessage({ role: "user", content: "\u{274C} Iptal ettim" });
    sendMessage("[[CHAT_ACTION:single_apply_cancel]]", { hidden: true });
  }, [addLocalMessage, sendMessage]);

  const handleExport = useCallback(() => {
    exportChatAsText(messages, displayProductName);
  }, [messages, displayProductName]);

  return (
    <div
      className="enterprise-surface flex h-full flex-col overflow-hidden rounded-2xl"
      style={{
        background: "linear-gradient(180deg, rgba(15,23,42,0.92), rgba(2,6,23,0.95))",
        border: "1px solid rgba(148,163,184,0.2)",
        boxShadow: "0 24px 52px rgba(2, 6, 23, 0.52)",
      }}
    >
      <ChatHeader
        displayProductName={displayProductName}
        displayProductCategory={displayProductCategory}
        displaySeoScore={displaySeoScore}
        productDetailUrl={productDetailUrl}
        availableSkills={chatSkills}
        activeSkill={activeSkill}
        skillLoading={skillsQ.isLoading}
        onSkillSelect={setActiveSkill}
        onSkillClear={clearActiveSkill}
        hasMessages={messages.length > 0}
        onClear={clearHistory}
        onExport={handleExport}
      />

      {isReconnecting && <ReconnectingBanner />}

      <ChatMessages
        score={score}
        product={product}
        productId={productId}
        showStarterState={showStarterState}
        isLoading={isLoading}
        isInspectingProduct={isInspectingProduct}
        isAutoIntroActive={isAutoIntroActive}
        messages={messages}
        assistantLabel={assistantLabel}
        liveContextLength={liveContextLength}
        liveElapsedSeconds={liveElapsedSeconds}
        starterPrompts={starterPromptsOverride}
        onStarterPrompt={handleStarterPrompt}
        onApplyOption={handleApplySuggestionOption}
        onRetry={retryLastMessage}
      />

      <ChatInput
        product={product}
        score={score}
        productId={productId}
        displayProductName={displayProductName}
        isLoading={isLoading}
        isAutoIntroActive={isAutoIntroActive}
        sessionStatusItems={sessionStatusItems}
        onSend={handleSend}
        onCancel={cancelMessage}
      />

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

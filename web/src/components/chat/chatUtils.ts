import type { ChatResponseMeta } from '../../types';
import { formatDuration, formatCompactNumber } from '../../shared/format/formatters';

// Re-export formatters so existing consumers don't break
export { formatDuration, formatCompactNumber, formatThoughtDuration, formatPercent } from '../../shared/format/formatters';

// ── Meta helpers ──────────────────────────────────────────────────────────────

function clampPercent(value: number) {
  return Math.min(100, Math.max(0, value));
}

export function readMetaNumber(meta: ChatResponseMeta | undefined, key: keyof ChatResponseMeta) {
  const value = meta?.[key];
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

export function resolveContextUsage(meta?: ChatResponseMeta, fallbackContextLength?: number | null) {
  const inputTokens = readMetaNumber(meta, 'input_tokens');
  const contextLength = readMetaNumber(meta, 'context_length') ?? fallbackContextLength ?? undefined;
  const usedPercent = readMetaNumber(meta, 'context_used_percent');
  const remainingPercent = readMetaNumber(meta, 'context_remaining_percent');

  if (typeof inputTokens !== 'number' || typeof contextLength !== 'number' || contextLength <= 0) {
    return null;
  }

  const derivedUsed = clampPercent((inputTokens / contextLength) * 100);
  const normalizedUsed = typeof usedPercent === 'number' ? clampPercent(usedPercent) : derivedUsed;
  const normalizedRemaining =
    typeof remainingPercent === 'number'
      ? clampPercent(remainingPercent)
      : clampPercent(100 - normalizedUsed);

  return {
    inputTokens,
    contextLength,
    usedPercent: normalizedUsed,
    remainingPercent: normalizedRemaining,
  };
}

export function getAssistantMetrics(meta?: ChatResponseMeta) {
  if (!meta) {
    return [];
  }

  const metrics: Array<{ key: string; label: string; value: string }> = [];
  const outputTokens = readMetaNumber(meta, 'output_tokens');
  const totalTokens = readMetaNumber(meta, 'total_tokens');
  const elapsedSeconds = readMetaNumber(meta, 'elapsed_seconds');
  let tokensPerSecond = readMetaNumber(meta, 'tokens_per_second');
  const ttft = readMetaNumber(meta, 'time_to_first_token_seconds');

  if (typeof totalTokens === 'number' && totalTokens > 0) {
    metrics.push({ key: 'tokens', label: 'Token', value: `${formatCompactNumber(totalTokens)} tok` });
  } else if (typeof outputTokens === 'number' && outputTokens > 0) {
    metrics.push({ key: 'tokens', label: 'Token', value: `${formatCompactNumber(outputTokens)} tok` });
  }

  if (typeof elapsedSeconds === 'number' && elapsedSeconds > 0) {
    metrics.push({ key: 'elapsed', label: 'Sure', value: formatDuration(elapsedSeconds) });
  }

  if (
    (typeof tokensPerSecond !== 'number' || tokensPerSecond <= 0)
    && typeof elapsedSeconds === 'number'
    && elapsedSeconds > 0
  ) {
    const rateBase = outputTokens ?? totalTokens;
    if (typeof rateBase === 'number' && rateBase > 0) {
      tokensPerSecond = rateBase / elapsedSeconds;
    }
  }

  if (typeof tokensPerSecond === 'number' && tokensPerSecond > 0) {
    const roundedRate =
      tokensPerSecond >= 100 ? Math.round(tokensPerSecond) : Number(tokensPerSecond.toFixed(1));
    metrics.push({ key: 'speed', label: 'Hiz', value: `${formatCompactNumber(roundedRate)} tok/sn` });
  }

  if (typeof ttft === 'number' && ttft > 0) {
    metrics.push({ key: 'ttft', label: 'TTFT', value: formatDuration(ttft) });
  }

  return metrics;
}

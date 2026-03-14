// ── Shared formatters (single source of truth) ──────────────────────────────

export function formatDuration(seconds: number) {
  const safeSeconds = Math.max(seconds, 0);
  if (safeSeconds < 60) {
    return safeSeconds < 10 ? `${safeSeconds.toFixed(2)}s` : `${safeSeconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = Math.floor(safeSeconds % 60);
  return `${minutes}m ${remainder}s`;
}

export function formatCompactNumber(value: number) {
  if (value >= 1000) {
    return value >= 10_000 ? `${Math.round(value / 1000)}K` : `${(value / 1000).toFixed(1)}K`;
  }
  return String(value);
}

export function formatThoughtDuration(seconds: number) {
  const safeSeconds = Math.max(seconds, 0);
  if (safeSeconds < 60) {
    return `${safeSeconds.toFixed(2)} seconds`;
  }
  return formatDuration(safeSeconds);
}

export function formatPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

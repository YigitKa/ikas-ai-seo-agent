import { useState } from 'react';
import type { ToolResult } from '../../../types';

// ── SEO agent tool metadata ───────────────────────────────────────────────────

const SEO_AGENT_TOOLS: Record<string, { label: string; icon: string }> = {
  seo_score_product: {
    label: 'SEO Puanlama',
    icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  },
  validate_rewrite: {
    label: 'Yeniden Yazım Doğrulama',
    icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  save_suggestion: {
    label: 'Öneri Kaydedildi',
    icon: 'M5 13l4 4L19 7',
  },
  get_product_details: {
    label: 'Ürün Detayları Alındı',
    icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  get_seo_guidelines: {
    label: 'SEO Kılavuzları',
    icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
  },
  search_products: {
    label: 'Ürün Arama',
    icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
  },
};

// ── Score extraction helpers ──────────────────────────────────────────────────

function extractSeoScoreResult(resultJson: string): { score?: number; previous?: number } | null {
  try {
    const parsed = JSON.parse(resultJson);
    if (typeof parsed?.total_score === 'number') {
      return { score: parsed.total_score };
    }
    // Sometimes result is wrapped: { score: { total_score: 72 }, previous_score: 65 }
    if (typeof parsed?.score?.total_score === 'number') {
      return {
        score: parsed.score.total_score,
        previous: typeof parsed.previous_score === 'number' ? parsed.previous_score : undefined,
      };
    }
    // Flat result string like "Total score: 72/100"
    const match = String(resultJson).match(/(\d+)\s*\/\s*100/);
    if (match) return { score: parseInt(match[1]) };
  } catch {
    const match = String(resultJson).match(/(\d+)\s*\/\s*100/);
    if (match) return { score: parseInt(match[1]) };
  }
  return null;
}

function extractValidateResult(resultJson: string): { improved: boolean; delta?: number } | null {
  try {
    const parsed = JSON.parse(resultJson);
    if (typeof parsed?.improved === 'boolean') {
      return {
        improved: parsed.improved,
        delta: typeof parsed.score_delta === 'number' ? parsed.score_delta : undefined,
      };
    }
    const text = String(resultJson).toLowerCase();
    const improved = text.includes('improved') || text.includes('iyilesti') || text.includes('artis');
    return { improved };
  } catch {
    const text = String(resultJson).toLowerCase();
    const improved = text.includes('improved') || text.includes('iyilesti');
    return { improved };
  }
}

// ── SEO Agent Tool Card ───────────────────────────────────────────────────────

function SeoAgentToolCard({ result, toolMeta }: { result: ToolResult; toolMeta: { label: string; icon: string } }) {
  const [expanded, setExpanded] = useState(false);

  // Parse specialized result data
  const scoreResult =
    result.tool === 'seo_score_product' ? extractSeoScoreResult(result.result) : null;
  const validateResult =
    result.tool === 'validate_rewrite' ? extractValidateResult(result.result) : null;
  const isSaved = result.tool === 'save_suggestion';

  // Color themes per tool
  const colorMap: Record<string, { bg: string; border: string; icon: string; badge: string }> = {
    seo_score_product: {
      bg: 'rgba(99, 102, 241, 0.06)',
      border: 'rgba(99, 102, 241, 0.18)',
      icon: '#818cf8',
      badge: 'rgba(99, 102, 241, 0.18)',
    },
    validate_rewrite: {
      bg: validateResult?.improved === false
        ? 'rgba(245, 158, 11, 0.06)'
        : 'rgba(16, 185, 129, 0.06)',
      border: validateResult?.improved === false
        ? 'rgba(245, 158, 11, 0.2)'
        : 'rgba(16, 185, 129, 0.2)',
      icon: validateResult?.improved === false ? '#fbbf24' : '#34d399',
      badge: validateResult?.improved === false
        ? 'rgba(245, 158, 11, 0.18)'
        : 'rgba(16, 185, 129, 0.18)',
    },
    save_suggestion: {
      bg: 'rgba(16, 185, 129, 0.06)',
      border: 'rgba(16, 185, 129, 0.2)',
      icon: '#34d399',
      badge: 'rgba(16, 185, 129, 0.18)',
    },
    default: {
      bg: 'rgba(99, 102, 241, 0.04)',
      border: 'rgba(99, 102, 241, 0.14)',
      icon: '#818cf8',
      badge: 'rgba(99, 102, 241, 0.14)',
    },
  };

  const colors = colorMap[result.tool] ?? colorMap.default;

  let parsed: string;
  try {
    parsed = JSON.stringify(JSON.parse(result.result), null, 2);
  } catch {
    parsed = result.result;
  }

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{ background: colors.bg, border: `1px solid ${colors.border}` }}
    >
      <div className="flex items-center gap-2">
        <svg
          className="h-3.5 w-3.5 flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          style={{ color: colors.icon }}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d={toolMeta.icon} />
        </svg>

        <span className="font-semibold" style={{ color: colors.icon }}>
          {toolMeta.label}
        </span>

        {/* Score badge for seo_score_product */}
        {scoreResult?.score !== undefined && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{ background: colors.badge, color: colors.icon }}
          >
            {scoreResult.score}/100
            {scoreResult.previous !== undefined && scoreResult.previous !== scoreResult.score && (
              <span className="ml-1 opacity-70">
                (önceki: {scoreResult.previous})
              </span>
            )}
          </span>
        )}

        {/* Validate result badge */}
        {validateResult !== null && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{ background: colors.badge, color: colors.icon }}
          >
            {validateResult.improved
              ? `✓ İyileşme${validateResult.delta !== undefined && validateResult.delta > 0 ? ` (+${validateResult.delta})` : ''}`
              : '↻ Devam ediyor'}
          </span>
        )}

        {/* Save confirmation */}
        {isSaved && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{ background: colors.badge, color: colors.icon }}
          >
            ✓ Kaydedildi
          </span>
        )}

        {/* Expand toggle (only for non-save tools) */}
        {!isSaved && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="ml-auto text-[10px] transition-opacity hover:opacity-70"
            style={{ color: 'rgba(255,255,255,0.3)' }}
          >
            {expanded ? 'Gizle' : 'Detay'}
          </button>
        )}
      </div>

      {expanded && (
        <pre
          className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md p-2 text-[11px]"
          style={{ background: 'rgba(0,0,0,0.2)', color: 'rgba(255,255,255,0.5)' }}
        >
          {parsed}
        </pre>
      )}
    </div>
  );
}

// ── MCP Tool Card (existing style) ───────────────────────────────────────────

function McpToolCard({ result }: { result: ToolResult }) {
  const [expanded, setExpanded] = useState(false);
  let parsed: string;
  try {
    parsed = JSON.stringify(JSON.parse(result.result), null, 2);
  } catch {
    parsed = result.result;
  }

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{ background: 'rgba(245, 158, 11, 0.06)', border: '1px solid rgba(245, 158, 11, 0.15)' }}
    >
      <div
        className="mb-1 px-0.5 text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'rgba(245, 158, 11, 0.72)' }}
      >
        ikas MCP
      </div>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left"
        style={{ color: '#fbbf24' }}
      >
        <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <span className="font-mono font-semibold">{result.tool}</span>
        <span style={{ color: 'rgba(245, 158, 11, 0.5)' }}>
          ({Object.keys(result.arguments).length} arg)
        </span>
        <span className="ml-auto text-[10px]" style={{ color: 'rgba(245, 158, 11, 0.6)' }}>
          {expanded ? 'Gizle' : 'Goster'}
        </span>
      </button>
      {expanded && (
        <pre
          className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md p-2 text-[11px]"
          style={{ background: 'rgba(0,0,0,0.2)', color: 'rgba(245, 158, 11, 0.7)' }}
        >
          {parsed}
        </pre>
      )}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function ToolResultCard({ result }: { result: ToolResult }) {
  const seoMeta = SEO_AGENT_TOOLS[result.tool];
  if (seoMeta) {
    return <SeoAgentToolCard result={result} toolMeta={seoMeta} />;
  }
  return <McpToolCard result={result} />;
}

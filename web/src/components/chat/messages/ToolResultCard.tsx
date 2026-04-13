import { useMemo, useState } from 'react';
import type { ToolResult, ToolResultEnvelope } from '../../../types';

const SEO_AGENT_TOOLS: Record<string, { label: string; icon: string }> = {
  seo_score_product: {
    label: 'SEO Puanlama',
    icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  },
  validate_rewrite: {
    label: 'Yeniden Yazim Dogrulama',
    icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  save_suggestion: {
    label: 'Oneri Kaydedildi',
    icon: 'M5 13l4 4L19 7',
  },
  get_product_details: {
    label: 'Urun Detaylari Alindi',
    icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  get_seo_guidelines: {
    label: 'SEO Kilavuzlari',
    icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
  },
  search_products: {
    label: 'Urun Arama',
    icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
  },
  competitor_price_research: {
    label: 'Rakip Fiyat Arastirmasi',
    icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
};

function unwrapToolEnvelope(resultJson: string): { payload: unknown; envelope: ToolResultEnvelope | null } {
  try {
    const parsed = JSON.parse(resultJson);
    if (
      parsed
      && typeof parsed === 'object'
      && 'ok' in parsed
      && 'tool_name' in parsed
      && 'meta' in parsed
    ) {
      const envelope = parsed as ToolResultEnvelope;
      return {
        payload: envelope.ok ? envelope.data : envelope,
        envelope,
      };
    }
    return { payload: parsed, envelope: null };
  } catch {
    return { payload: resultJson, envelope: null };
  }
}

function formatToolPayload(resultJson: string): string {
  const { payload } = unwrapToolEnvelope(resultJson);
  if (typeof payload === 'string') return payload;
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

function extractSeoScoreResult(resultJson: string): { score?: number; previous?: number } | null {
  const { payload } = unwrapToolEnvelope(resultJson);
  if (payload && typeof payload === 'object') {
    const parsed = payload as { total_score?: number; score?: { total_score?: number }; previous_score?: number };
    if (typeof parsed.total_score === 'number') {
      return { score: parsed.total_score };
    }
    if (typeof parsed.score?.total_score === 'number') {
      return {
        score: parsed.score.total_score,
        previous: typeof parsed.previous_score === 'number' ? parsed.previous_score : undefined,
      };
    }
  }
  const match = String(resultJson).match(/(\d+)\s*\/\s*100/);
  if (match) return { score: parseInt(match[1], 10) };
  return null;
}

function extractValidateResult(resultJson: string): { improved: boolean; delta?: number } | null {
  const { payload } = unwrapToolEnvelope(resultJson);
  if (payload && typeof payload === 'object') {
    const parsed = payload as { improved?: boolean; score_delta?: number };
    if (typeof parsed.improved === 'boolean') {
      return {
        improved: parsed.improved,
        delta: typeof parsed.score_delta === 'number' ? parsed.score_delta : undefined,
      };
    }
  }
  const text = String(resultJson).toLowerCase();
  const improved = text.includes('improved') || text.includes('iyilesti') || text.includes('artis');
  return { improved };
}

function extractPriceResearchResult(resultJson: string): {
  position?: string;
  count?: number;
  avgPrice?: number;
  ourPrice?: number;
} | null {
  const { payload } = unwrapToolEnvelope(resultJson);
  if (payload && typeof payload === 'object') {
    const p = payload as {
      price_position?: string;
      competitor_count?: number;
      average_price?: number;
      our_price?: number;
    };
    if (p.competitor_count !== undefined || p.price_position) {
      return {
        position: p.price_position,
        count: p.competitor_count,
        avgPrice: p.average_price,
        ourPrice: p.our_price,
      };
    }
  }
  return null;
}

const POSITION_LABELS: Record<string, { text: string; color: string }> = {
  en_ucuz: { text: 'En Ucuz', color: 'var(--color-icon-success)' },
  ortalama_alti: { text: 'Ort. Alti', color: 'var(--color-icon-success)' },
  ortalama: { text: 'Ortalama', color: 'var(--color-icon-warning)' },
  ortalama_ustu: { text: 'Ort. Ustu', color: 'var(--color-orange)' },
  en_pahali: { text: 'En Pahali', color: 'var(--color-danger)' },
};

function isSavedResult(resultJson: string): boolean {
  const { envelope } = unwrapToolEnvelope(resultJson);
  if (!envelope || !envelope.ok || !envelope.data || typeof envelope.data !== 'object') {
    return false;
  }
  return 'success' in envelope.data || 'suggestion_saved' in envelope.data;
}

function LazyToolPayload({ expanded, resultJson, tone }: { expanded: boolean; resultJson: string; tone: string }) {
  const parsed = useMemo(() => {
    if (!expanded) {
      return '';
    }
    return formatToolPayload(resultJson);
  }, [expanded, resultJson]);

  if (!expanded) {
    return null;
  }

  return (
    <pre
      className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md p-2 text-[11px]"
      style={{ background: 'rgba(0,0,0,0.2)', color: tone }}
    >
      {parsed}
    </pre>
  );
}

function SeoAgentToolCard({ result, toolMeta }: { result: ToolResult; toolMeta: { label: string; icon: string } }) {
  const [expanded, setExpanded] = useState(false);
  const scoreResult = result.tool === 'seo_score_product' ? extractSeoScoreResult(result.result) : null;
  const validateResult = result.tool === 'validate_rewrite' ? extractValidateResult(result.result) : null;
  const isSaved = result.tool === 'save_suggestion' && isSavedResult(result.result);
  const priceResult = result.tool === 'competitor_price_research' ? extractPriceResearchResult(result.result) : null;

  const colorMap: Record<string, { bg: string; border: string; icon: string; badge: string }> = {
    seo_score_product: {
      bg: 'var(--tint-primary-bg)',
      border: 'var(--tint-primary-soft)',
      icon: 'var(--color-primary-light)',
      badge: 'var(--tint-primary-soft)',
    },
    validate_rewrite: {
      bg: validateResult?.improved === false
        ? 'var(--tint-warning-bg)'
        : 'var(--tint-success-bg)',
      border: validateResult?.improved === false
        ? 'var(--tint-warning-soft)'
        : 'var(--tint-success-soft)',
      icon: validateResult?.improved === false ? 'var(--color-icon-warning)' : 'var(--color-icon-success)',
      badge: validateResult?.improved === false
        ? 'var(--tint-warning-soft)'
        : 'var(--tint-success-soft)',
    },
    save_suggestion: {
      bg: 'var(--tint-success-bg)',
      border: 'var(--tint-success-soft)',
      icon: 'var(--color-icon-success)',
      badge: 'var(--tint-success-soft)',
    },
    competitor_price_research: {
      bg: 'var(--tint-warning-bg)',
      border: 'var(--tint-warning-soft)',
      icon: 'var(--color-warning)',
      badge: 'var(--tint-warning-soft)',
    },
    default: {
      bg: 'var(--tint-primary-bg)',
      border: 'var(--tint-primary-soft)',
      icon: 'var(--color-primary-light)',
      badge: 'var(--tint-primary-soft)',
    },
  };

  const colors = colorMap[result.tool] ?? colorMap.default;

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

        {scoreResult?.score !== undefined && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{ background: colors.badge, color: colors.icon }}
          >
            {scoreResult.score}/100
            {scoreResult.previous !== undefined && scoreResult.previous !== scoreResult.score && (
              <span className="ml-1 opacity-70">
                (onceki: {scoreResult.previous})
              </span>
            )}
          </span>
        )}

        {validateResult !== null && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{ background: colors.badge, color: colors.icon }}
          >
            {validateResult.improved
              ? `Iyilesme${validateResult.delta !== undefined && validateResult.delta > 0 ? ` (+${validateResult.delta})` : ''}`
              : 'Devam ediyor'}
          </span>
        )}

        {priceResult !== null && (
          <span
            className="ml-auto flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{
              background: colors.badge,
              color: priceResult.position
                ? (POSITION_LABELS[priceResult.position]?.color ?? colors.icon)
                : colors.icon,
            }}
          >
            {priceResult.position && POSITION_LABELS[priceResult.position]
              ? POSITION_LABELS[priceResult.position].text
              : 'Sonuc'}
            {priceResult.count !== undefined && priceResult.count > 0 && (
              <span className="opacity-70">({priceResult.count} rakip)</span>
            )}
          </span>
        )}

        {isSaved && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{ background: colors.badge, color: colors.icon }}
          >
            Kaydedildi
          </span>
        )}

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

      <LazyToolPayload
        expanded={expanded}
        resultJson={result.result}
        tone="rgba(255,255,255,0.5)"
      />
    </div>
  );
}

function McpToolCard({ result }: { result: ToolResult }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{ background: 'var(--tint-warning-bg)', border: '1px solid var(--tint-warning-soft)' }}
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
        style={{ color: 'var(--color-icon-warning)' }}
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
      <LazyToolPayload
        expanded={expanded}
        resultJson={result.result}
        tone="rgba(245, 158, 11, 0.7)"
      />
    </div>
  );
}

export default function ToolResultCard({ result }: { result: ToolResult }) {
  const seoMeta = SEO_AGENT_TOOLS[result.tool];
  if (seoMeta) {
    return <SeoAgentToolCard result={result} toolMeta={seoMeta} />;
  }
  return <McpToolCard result={result} />;
}

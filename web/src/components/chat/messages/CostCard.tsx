import type { ChatResponseMeta } from '../../../types';

function formatCost(cost: number): string {
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

export default function CostCard({
  meta,
}: {
  meta?: ChatResponseMeta;
}) {
  const cost = meta?.estimated_cost;
  const sessionCost = meta?.session_total_cost;
  const inputTokens = meta?.input_tokens;
  const outputTokens = meta?.output_tokens;

  if (!cost && !sessionCost) return null;

  return (
    <div
      className="mr-6 rounded-xl p-3"
      style={{ background: 'rgba(255,255,255,0.035)', border: '1px solid rgba(255,255,255,0.08)' }}
    >
      <div className="space-y-1.5 text-[12px] leading-5">
        {cost != null && cost > 0 ? (
          <div style={{ color: 'var(--color-text-secondary)' }}>
            This message cost:{' '}
            <span className="font-semibold text-emerald-400">{formatCost(cost)}</span>
            {inputTokens != null && outputTokens != null ? (
              <span style={{ color: 'var(--color-text-muted)' }}>
                {' '}({inputTokens.toLocaleString()} in + {outputTokens.toLocaleString()} out)
              </span>
            ) : null}
          </div>
        ) : null}
        {sessionCost != null && sessionCost > 0 ? (
          <div style={{ color: 'var(--color-text-secondary)' }}>
            Session total:{' '}
            <span className="font-semibold text-amber-400">{formatCost(sessionCost)}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

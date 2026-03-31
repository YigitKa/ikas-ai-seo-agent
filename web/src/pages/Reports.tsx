import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, Cell, Area, AreaChart,
  PieChart, Pie,
} from 'recharts';
import AppHeader from '../shared/ui/AppHeader';
import { EnterpriseButton, EnterpriseSurface } from '../shared/ui/EnterprisePrimitives';
import { useToast } from '../shared/ui/Toast';
import {
  getStoreTrends, getReportSummary, getTopImprovers, takeSnapshot, getProductTrends,
  getScoreChangeLog, getScoreChangeSummary, getHourlyActivity, getDailyActivity,
  getScoreDistribution, getOperationMetrics,
} from '../api/client';
import type { DailyStoreTrend, ReportSummary, TopImprover } from '../types';

type DateRange = 7 | 30 | 90 | 365;

const C = {
  primary: '#60a5fa',
  success: '#34d399',
  warning: '#fbbf24',
  danger: '#f87171',
  purple: '#a78bfa',
  cyan: '#22d3ee',
  pink: '#f472b6',
  orange: '#fb923c',
  grid: 'rgba(148,163,184,0.08)',
  border: 'rgba(148,163,184,0.12)',
  muted: 'rgba(148,163,184,0.5)',
  dimmed: 'rgba(148,163,184,0.3)',
  text: '#e2e8f0',
};

const OP_LABELS: Record<string, string> = {
  apply: 'Tekil',
  batch_apply: 'Toplu',
  rollback: 'Geri Al',
};

const OP_COLORS: Record<string, string> = {
  apply: C.success,
  batch_apply: C.primary,
  rollback: C.danger,
};

const BUCKET_COLORS: Record<string, string> = {
  '90-100': C.success,
  '80-89': C.primary,
  '70-79': C.cyan,
  '60-69': C.warning,
  '50-59': C.orange,
  '0-49': C.danger,
};

function fmtDate(d: unknown) {
  if (typeof d !== 'string') return '';
  return new Date(d.includes('T') ? d : d + 'T00:00:00').toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' });
}

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

function defaultRange(): { start: string; end: string } {
  const now = new Date();
  return {
    end: now.toISOString().slice(0, 10),
    start: new Date(now.getTime() - 30 * 86400000).toISOString().slice(0, 10),
  };
}

// ── Shared tooltip style ─────────────────────────────────────────────────────

const tooltipStyle = {
  contentStyle: {
    background: 'rgba(2,6,23,0.96)',
    border: `1px solid ${C.border}`,
    borderRadius: 10,
    color: C.text,
    fontSize: 11,
    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
  },
};

// ── KPI Card ─────────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, color, icon }: {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  icon?: React.ReactNode;
}) {
  return (
    <EnterpriseSurface className="p-4 relative overflow-hidden">
      {icon && (
        <div className="absolute top-3 right-3 opacity-10" style={{ color: color || C.primary }}>
          {icon}
        </div>
      )}
      <div className="text-[10px] font-semibold uppercase tracking-wider mb-2" style={{ color: C.muted }}>
        {label}
      </div>
      <div className="text-2xl font-extrabold tabular-nums" style={{ color: color || C.text }}>
        {value}
      </div>
      {sub && (
        <div className="text-[10px] mt-1" style={{ color: C.dimmed }}>{sub}</div>
      )}
    </EnterpriseSurface>
  );
}

// ── Score Delta Badge ────────────────────────────────────────────────────────

function DeltaBadge({ value, size = 'sm' }: { value: number; size?: 'sm' | 'lg' }) {
  const color = value > 0 ? C.success : value < 0 ? C.danger : C.muted;
  const bg = value > 0 ? 'rgba(52,211,153,0.12)' : value < 0 ? 'rgba(248,113,113,0.12)' : 'rgba(148,163,184,0.08)';
  const fontSize = size === 'lg' ? 14 : 11;
  return (
    <span
      className="inline-flex items-center rounded-md px-1.5 py-0.5 font-bold tabular-nums"
      style={{ color, background: bg, fontSize }}
    >
      {value > 0 ? '+' : ''}{value}
    </span>
  );
}

// ── Section Header ───────────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: C.muted }}>
      {children}
    </h3>
  );
}

// ── Daily Activity Chart ─────────────────────────────────────────────────────

function DailyActivityChart({ data }: { data: Array<{ day: string; event_count: number; avg_delta: number | null; improved: number; degraded: number; unique_products: number }> }) {
  if (data.length === 0) return <EmptyChart text="Bu donemde gunluk aktivite yok" />;

  return (
    <EnterpriseSurface className="p-5">
      <SectionTitle>Gunluk Aktivite</SectionTitle>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data} margin={{ left: 0, right: 0 }}>
          <defs>
            <linearGradient id="gradImproved" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.success} stopOpacity={0.3} />
              <stop offset="100%" stopColor={C.success} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradDegraded" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.danger} stopOpacity={0.2} />
              <stop offset="100%" stopColor={C.danger} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
          <XAxis dataKey="day" tickFormatter={fmtDate} tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} />
          <YAxis tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} allowDecimals={false} />
          <Tooltip
            {...tooltipStyle}
            labelFormatter={(label: unknown) => typeof label === 'string' ? fmtDate(label) : ''}
            formatter={(val: unknown, name: unknown) => {
              const labels: Record<string, string> = { improved: 'Iyilesen', degraded: 'Gerileyen', event_count: 'Toplam Islem' };
              return [Number(val), labels[String(name)] ?? String(name)];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: C.muted }} formatter={(v: string) => ({ improved: 'Iyilesen', degraded: 'Gerileyen', event_count: 'Toplam' }[v] ?? v)} />
          <Area type="monotone" dataKey="improved" stroke={C.success} strokeWidth={2} fill="url(#gradImproved)" />
          <Area type="monotone" dataKey="degraded" stroke={C.danger} strokeWidth={1.5} fill="url(#gradDegraded)" />
          <Line type="monotone" dataKey="event_count" stroke={C.primary} strokeWidth={2} strokeDasharray="4 2" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </EnterpriseSurface>
  );
}

// ── Hourly Activity Chart ────────────────────────────────────────────────────

function HourlyActivityChart({ data }: { data: Array<{ hour: string; event_count: number; avg_delta: number | null; improved: number; degraded: number }> }) {
  // Fill in all 24 hours
  const fullData = useMemo(() => {
    const map = new Map(data.map(d => [d.hour, d]));
    return Array.from({ length: 24 }, (_, i) => {
      const h = String(i).padStart(2, '0');
      return map.get(h) ?? { hour: h, event_count: 0, avg_delta: null, improved: 0, degraded: 0 };
    });
  }, [data]);

  const hasData = data.length > 0;
  if (!hasData) return <EmptyChart text="Bu donemde saatlik aktivite yok" />;

  return (
    <EnterpriseSurface className="p-5">
      <SectionTitle>Saatlik Aktivite Dagilimi</SectionTitle>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={fullData} margin={{ left: 0, right: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
          <XAxis dataKey="hour" tick={{ fill: C.muted, fontSize: 9 }} stroke={C.grid} tickFormatter={(h: string) => `${h}:00`} />
          <YAxis tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} allowDecimals={false} />
          <Tooltip
            {...tooltipStyle}
            labelFormatter={(h: unknown) => `${h}:00 - ${h}:59`}
            formatter={(val: unknown, name: unknown) => {
              const labels: Record<string, string> = { improved: 'Iyilesen', degraded: 'Gerileyen' };
              return [Number(val), labels[String(name)] ?? String(name)];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: C.muted }} formatter={(v: string) => ({ improved: 'Iyilesen', degraded: 'Gerileyen' }[v] ?? v)} />
          <Bar dataKey="improved" stackId="a" fill={C.success} fillOpacity={0.7} radius={[0, 0, 0, 0]} maxBarSize={20} />
          <Bar dataKey="degraded" stackId="a" fill={C.danger} fillOpacity={0.7} radius={[3, 3, 0, 0]} maxBarSize={20} />
        </BarChart>
      </ResponsiveContainer>
    </EnterpriseSurface>
  );
}

// ── Score Distribution Chart ─────────────────────────────────────────────────

function ScoreDistributionChart({ data }: { data: Array<{ bucket: string; count: number }> }) {
  if (data.length === 0) return <EmptyChart text="Skor verisi yok" />;

  const total = data.reduce((s, d) => s + d.count, 0);

  return (
    <EnterpriseSurface className="p-5">
      <SectionTitle>Skor Dagilimi</SectionTitle>
      <div className="flex items-center gap-6">
        <div style={{ width: 140, height: 140 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                dataKey="count"
                nameKey="bucket"
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={65}
                strokeWidth={1}
                stroke="rgba(2,6,23,0.5)"
              >
                {data.map((d) => <Cell key={d.bucket} fill={BUCKET_COLORS[d.bucket] ?? C.muted} />)}
              </Pie>
              <Tooltip
                {...tooltipStyle}
                formatter={(val: unknown, name: unknown) => [`${Number(val)} urun (${total ? Math.round(Number(val) / total * 100) : 0}%)`, String(name)]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-1.5">
          {data.map(d => {
            const pct = total ? (d.count / total * 100) : 0;
            return (
              <div key={d.bucket} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: BUCKET_COLORS[d.bucket] ?? C.muted }} />
                <span className="text-[11px] font-medium w-12" style={{ color: C.text }}>{d.bucket}</span>
                <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(148,163,184,0.06)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: BUCKET_COLORS[d.bucket] ?? C.muted }} />
                </div>
                <span className="text-[10px] tabular-nums font-bold w-8 text-right" style={{ color: C.text }}>{d.count}</span>
                <span className="text-[9px] tabular-nums w-9 text-right" style={{ color: C.dimmed }}>{pct.toFixed(0)}%</span>
              </div>
            );
          })}
        </div>
      </div>
    </EnterpriseSurface>
  );
}

// ── Operation Metrics Card ───────────────────────────────────────────────────

function OperationMetricsCard({ data }: { data: Array<{ operation: string; total: number; avg_delta: number | null; success_rate: number | null; best_delta: number | null; worst_delta: number | null; avg_score_after: number | null }> }) {
  if (data.length === 0) return null;

  return (
    <EnterpriseSurface className="p-5">
      <SectionTitle>Islem Bazli Performans</SectionTitle>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {data.map(op => {
          const label = OP_LABELS[op.operation] ?? op.operation;
          const color = OP_COLORS[op.operation] ?? C.muted;
          const rate = op.success_rate ?? 0;
          return (
            <div key={op.operation} className="rounded-xl p-4" style={{ background: 'rgba(15,23,42,0.5)', border: `1px solid ${C.border}` }}>
              <div className="flex items-center gap-2 mb-3">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                <span className="text-xs font-bold uppercase tracking-wide" style={{ color }}>{label}</span>
                <span className="ml-auto text-lg font-extrabold tabular-nums" style={{ color: C.text }}>{op.total}</span>
              </div>
              {/* Success rate bar */}
              <div className="mb-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[9px] uppercase tracking-wider" style={{ color: C.muted }}>Basari Orani</span>
                  <span className="text-[11px] font-bold tabular-nums" style={{ color: rate >= 70 ? C.success : rate >= 40 ? C.warning : C.danger }}>{rate}%</span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(148,163,184,0.06)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${rate}%`, background: rate >= 70 ? C.success : rate >= 40 ? C.warning : C.danger }} />
                </div>
              </div>
              {/* Stats row */}
              <div className="grid grid-cols-3 gap-2 mt-3">
                <div>
                  <div className="text-[9px] uppercase" style={{ color: C.dimmed }}>Ort.</div>
                  <div className="text-[11px] font-bold tabular-nums" style={{ color: (op.avg_delta ?? 0) >= 0 ? C.success : C.danger }}>
                    {op.avg_delta != null ? `${op.avg_delta > 0 ? '+' : ''}${op.avg_delta}` : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] uppercase" style={{ color: C.dimmed }}>En Iyi</div>
                  <div className="text-[11px] font-bold tabular-nums" style={{ color: C.success }}>
                    {op.best_delta != null ? `+${op.best_delta}` : '—'}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] uppercase" style={{ color: C.dimmed }}>En Kotu</div>
                  <div className="text-[11px] font-bold tabular-nums" style={{ color: C.danger }}>
                    {op.worst_delta != null ? String(op.worst_delta) : '—'}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </EnterpriseSurface>
  );
}

// ── Score Change Delta Chart (bar chart) ─────────────────────────────────────

function ScoreChangeChart({ data }: { data: Array<{ product_name: string; delta: number | null; created_at: string; score_before: number | null; score_after: number | null }> }) {
  const chartData = useMemo(() => {
    return [...data]
      .reverse()
      .map((d, i) => ({
        idx: i,
        name: d.product_name,
        delta: d.delta ?? 0,
        before: d.score_before,
        after: d.score_after,
        date: fmtDateTime(d.created_at),
      }));
  }, [data]);

  if (chartData.length === 0) return null;

  return (
    <EnterpriseSurface className="p-5">
      <SectionTitle>Skor Degisim Grafigi</SectionTitle>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ left: 0, right: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: C.muted, fontSize: 10 }}
            stroke={C.grid}
            interval="preserveStartEnd"
          />
          <YAxis tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} />
          <Tooltip
            {...tooltipStyle}
            formatter={(val: unknown) => {
              const v = Number(val);
              return [`${v > 0 ? '+' : ''}${v} puan`, 'Degisim'];
            }}
            labelFormatter={(_: unknown, payload: readonly { payload?: Record<string, unknown> }[]) => {
              const p = payload?.[0]?.payload;
              return p ? `${p.name ?? ''} — ${p.date ?? ''}` : '';
            }}
          />
          <Bar dataKey="delta" radius={[4, 4, 0, 0]} maxBarSize={32}>
            {chartData.map((d, i) => (
              <Cell
                key={i}
                fill={d.delta > 0 ? C.success : d.delta < 0 ? C.danger : C.dimmed}
                fillOpacity={0.8}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </EnterpriseSurface>
  );
}

// ── Store Trend Chart ────────────────────────────────────────────────────────

function StoreTrendChart({ data, range, onRangeChange }: {
  data: DailyStoreTrend[];
  range: DateRange;
  onRangeChange: (r: DateRange) => void;
}) {
  const ranges: DateRange[] = [7, 30, 90, 365];
  const labels: Record<DateRange, string> = { 7: '7G', 30: '30G', 90: '90G', 365: '1Y' };

  return (
    <EnterpriseSurface className="p-5">
      <div className="flex items-center justify-between mb-4">
        <SectionTitle>Magaza Skor Trendi</SectionTitle>
        <div className="flex gap-0.5 rounded-lg p-0.5" style={{ background: 'rgba(148,163,184,0.06)' }}>
          {ranges.map(r => (
            <button
              key={r}
              onClick={() => onRangeChange(r)}
              className="px-2.5 py-1 rounded-md text-[10px] font-semibold transition-all"
              style={{
                background: r === range ? 'rgba(96,165,250,0.2)' : 'transparent',
                color: r === range ? C.primary : C.muted,
              }}
            >
              {labels[r]}
            </button>
          ))}
        </div>
      </div>

      {data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-xs" style={{ color: C.dimmed }}>
          Bu donemde trend verisi yok
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={C.primary} stopOpacity={0.3} />
                <stop offset="100%" stopColor={C.primary} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
            <XAxis dataKey="snapshot_date" tickFormatter={fmtDate} tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} />
            <YAxis domain={[0, 100]} tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} />
            <Tooltip {...tooltipStyle} labelFormatter={fmtDate} />
            <Legend wrapperStyle={{ fontSize: 11, color: C.muted }} />
            <Area type="monotone" dataKey="avg_total" name="Toplam" stroke={C.primary} strokeWidth={2.5} fill="url(#gradTotal)" dot={false} />
            <Line type="monotone" dataKey="avg_seo" name="SEO" stroke={C.success} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="avg_geo" name="GEO" stroke={C.purple} strokeWidth={1.5} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </EnterpriseSurface>
  );
}

// ── Top Improvers ────────────────────────────────────────────────────────────

function TopImproversCard({ improvers }: { improvers: TopImprover[] }) {
  if (improvers.length === 0) return null;

  return (
    <EnterpriseSurface className="p-5">
      <SectionTitle>En Cok Gelisen Urunler</SectionTitle>
      <div className="space-y-2.5">
        {improvers.slice(0, 10).map((item, i) => {
          const pct = Math.min(Math.max(item.delta, 0), 40) / 40 * 100;
          return (
            <div key={item.product_id} className="flex items-center gap-2.5">
              <span
                className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold"
                style={{
                  background: i < 3 ? 'rgba(52,211,153,0.15)' : 'rgba(148,163,184,0.08)',
                  color: i < 3 ? C.success : C.muted,
                }}
              >
                {i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-[11px] truncate font-medium" style={{ color: C.text }}>
                  {item.product_name}
                </div>
                <div className="mt-1 h-1 rounded-full overflow-hidden" style={{ background: 'rgba(148,163,184,0.06)' }}>
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${pct}%`,
                      background: `linear-gradient(90deg, ${C.success}, ${C.primary})`,
                    }}
                  />
                </div>
              </div>
              <div className="flex-shrink-0 flex items-center gap-1.5 text-[11px] tabular-nums">
                <span style={{ color: C.dimmed }}>{item.first_score}</span>
                <span style={{ color: C.dimmed }}>→</span>
                <span className="font-bold" style={{ color: C.text }}>{item.latest_score}</span>
                <DeltaBadge value={item.delta} />
              </div>
            </div>
          );
        })}
      </div>
    </EnterpriseSurface>
  );
}

// ── Sub-score comparison ─────────────────────────────────────────────────────

function SubScoreChart({ summary }: { summary: ReportSummary }) {
  if (!summary.first_date || summary.first_date === summary.latest_date) return null;

  const SUB_LABELS: Record<string, string> = {
    title: 'Baslik',
    description: 'Aciklama',
    meta: 'Meta',
    keyword: 'Keyword',
    content_quality: 'Icerik',
    technical_seo: 'Teknik',
    readability: 'Okunabilirlik',
    ai_citability: 'AI Citability',
  };

  const data = Object.entries(SUB_LABELS).map(([key, name]) => ({
    name,
    ilk: summary.first_avg[key] ?? 0,
    son: summary.latest_avg[key] ?? 0,
    delta: ((summary.latest_avg[key] ?? 0) - (summary.first_avg[key] ?? 0)),
  }));

  return (
    <EnterpriseSurface className="p-5">
      <SectionTitle>Alt Skor Karsilastirmasi</SectionTitle>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} layout="vertical" margin={{ left: 70, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.grid} horizontal={false} />
          <XAxis type="number" tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} />
          <YAxis type="category" dataKey="name" tick={{ fill: C.muted, fontSize: 10 }} stroke="transparent" width={65} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="ilk" name="Ilk" fill="rgba(148,163,184,0.15)" radius={[0, 3, 3, 0]} barSize={10} />
          <Bar dataKey="son" name="Son" fill={C.primary} radius={[0, 3, 3, 0]} barSize={10} />
        </BarChart>
      </ResponsiveContainer>
    </EnterpriseSurface>
  );
}

// ── Product Drill-Down ───────────────────────────────────────────────────────

function ProductDrillDown({ improvers, range }: { improvers: TopImprover[]; range: DateRange }) {
  const [selected, setSelected] = useState<string | null>(null);
  const { data: trend } = useQuery({
    queryKey: ['product-trend', selected, range],
    queryFn: () => getProductTrends(selected!, range),
    enabled: !!selected,
  });

  if (improvers.length === 0) return null;

  return (
    <EnterpriseSurface className="p-5">
      <SectionTitle>Urun Bazli Trend</SectionTitle>
      <select
        value={selected ?? ''}
        onChange={e => setSelected(e.target.value || null)}
        className="w-full px-3 py-2 rounded-lg text-xs mb-4"
        style={{ background: 'rgba(15,23,42,0.8)', border: `1px solid ${C.border}`, color: C.text }}
      >
        <option value="">Urun secin...</option>
        {improvers.map(p => (
          <option key={p.product_id} value={p.product_id}>{p.product_name}</option>
        ))}
      </select>

      {selected && trend && trend.length > 0 ? (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={trend}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
            <XAxis dataKey="snapshot_date" tickFormatter={fmtDate} tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} />
            <YAxis domain={[0, 100]} tick={{ fill: C.muted, fontSize: 10 }} stroke={C.grid} />
            <Tooltip {...tooltipStyle} labelFormatter={fmtDate} />
            <Line type="monotone" dataKey="total_score" name="Toplam" stroke={C.primary} strokeWidth={2.5} dot={false} />
            <Line type="monotone" dataKey="seo_score" name="SEO" stroke={C.success} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="geo_score" name="GEO" stroke={C.purple} strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      ) : selected ? (
        <div className="h-24 flex items-center justify-center text-xs" style={{ color: C.dimmed }}>
          Bu urun icin trend verisi yok
        </div>
      ) : null}
    </EnterpriseSurface>
  );
}

// ── Empty chart placeholder ──────────────────────────────────────────────────

function EmptyChart({ text }: { text: string }) {
  return (
    <EnterpriseSurface className="p-5">
      <div className="h-48 flex items-center justify-center text-xs" style={{ color: C.dimmed }}>
        {text}
      </div>
    </EnterpriseSurface>
  );
}

// ── Score Change Log Table ───────────────────────────────────────────────────

function ScoreChangeTable({ data, loading }: { data: Array<{
  id: number; product_name: string; operation: string;
  score_before: number | null; score_after: number | null;
  delta: number | null; created_at: string;
}>; loading: boolean }) {
  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center" style={{ color: C.dimmed }}>
        <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M12 2v4m0 12v4m-7-7H2m20 0h-3m-2.5-6.5L14 5m-4 14l-2.5 2.5m11-2.5L16 19M5 5l2.5 2.5" />
        </svg>
        Yukleniyor...
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4">
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style={{ background: 'rgba(96,165,250,0.08)' }}>
          <svg className="w-8 h-8" style={{ color: C.dimmed }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: C.text }}>
          Henuz skor degisimi kaydedilmedi
        </p>
        <p className="text-xs text-center max-w-xs" style={{ color: C.dimmed }}>
          Urunlerin SEO bilgilerini guncelleyip uyguladiginizda, her degisim burada anlik olarak kayit altina alinacak.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead>
          <tr style={{ borderBottom: `1px solid ${C.border}` }}>
            {['Tarih', 'Urun Adi', 'Islem', 'Onceki', 'Sonraki', 'Degisim'].map(h => (
              <th key={h} className="px-4 py-3 text-left font-semibold uppercase tracking-wider text-[10px]" style={{ color: C.muted }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map(entry => (
            <tr
              key={entry.id}
              style={{ borderBottom: '1px solid rgba(148,163,184,0.04)' }}
              className="transition-colors hover:bg-[rgba(96,165,250,0.03)]"
            >
              <td className="px-4 py-2.5 tabular-nums whitespace-nowrap" style={{ color: C.muted }}>
                {fmtDateTime(entry.created_at)}
              </td>
              <td className="px-4 py-2.5 max-w-[220px] truncate font-medium" style={{ color: C.text }}>
                {entry.product_name}
              </td>
              <td className="px-4 py-2.5">
                <span
                  className="inline-block rounded-md px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide"
                  style={{
                    background: `${OP_COLORS[entry.operation] ?? C.muted}15`,
                    color: OP_COLORS[entry.operation] ?? C.muted,
                  }}
                >
                  {OP_LABELS[entry.operation] ?? entry.operation}
                </span>
              </td>
              <td className="px-4 py-2.5 tabular-nums" style={{ color: C.muted }}>
                {entry.score_before ?? '—'}
              </td>
              <td className="px-4 py-2.5 tabular-nums font-bold" style={{ color: C.text }}>
                {entry.score_after ?? '—'}
              </td>
              <td className="px-4 py-2.5">
                {entry.delta != null ? <DeltaBadge value={entry.delta} /> : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function Reports() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [range, setRange] = useState<DateRange>(30);
  const defaults = defaultRange();
  const [startDate, setStartDate] = useState(defaults.start);
  const [endDate, setEndDate] = useState(defaults.end);
  const [opFilter, setOpFilter] = useState('');

  // ── Data queries ────────────────────────────────────────────────────────────
  const { data: summary } = useQuery({ queryKey: ['report-summary'], queryFn: getReportSummary });
  const { data: trends } = useQuery({ queryKey: ['store-trends', range], queryFn: () => getStoreTrends(range) });
  const { data: improvers } = useQuery({ queryKey: ['top-improvers'], queryFn: () => getTopImprovers(15) });

  const { data: changeLog, isLoading: logLoading } = useQuery({
    queryKey: ['score-change-log', startDate, endDate, opFilter],
    queryFn: () => getScoreChangeLog({
      start_date: startDate, end_date: endDate,
      operation: opFilter || undefined, limit: 500,
    }),
  });

  const { data: changeSummary } = useQuery({
    queryKey: ['score-change-summary', startDate, endDate],
    queryFn: () => getScoreChangeSummary({ start_date: startDate, end_date: endDate }),
  });

  const { data: hourlyActivity } = useQuery({
    queryKey: ['hourly-activity', startDate, endDate],
    queryFn: () => getHourlyActivity({ start_date: startDate, end_date: endDate }),
  });

  const { data: dailyActivity } = useQuery({
    queryKey: ['daily-activity', startDate, endDate],
    queryFn: () => getDailyActivity({ start_date: startDate, end_date: endDate }),
  });

  const { data: scoreDistribution } = useQuery({
    queryKey: ['score-distribution'],
    queryFn: getScoreDistribution,
  });

  const { data: operationMetrics } = useQuery({
    queryKey: ['operation-metrics', startDate, endDate],
    queryFn: () => getOperationMetrics({ start_date: startDate, end_date: endDate }),
  });

  const snapshotMut = useMutation({
    mutationFn: takeSnapshot,
    onSuccess: () => {
      toast.success('Snapshot olusturuldu');
      queryClient.invalidateQueries({ queryKey: ['report-summary'] });
      queryClient.invalidateQueries({ queryKey: ['store-trends'] });
      queryClient.invalidateQueries({ queryKey: ['top-improvers'] });
      queryClient.invalidateQueries({ queryKey: ['score-distribution'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const cs = changeSummary;
  const logData = changeLog ?? [];

  // Derived: overall success rate
  const totalOps = operationMetrics?.reduce((s, m) => s + m.total, 0) ?? 0;
  const totalImproved = operationMetrics?.reduce((s, m) => s + Math.round(m.total * (m.success_rate ?? 0) / 100), 0) ?? 0;
  const overallSuccessRate = totalOps > 0 ? Math.round(totalImproved / totalOps * 100) : 0;

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base, #020617)' }}>
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <AppHeader
        title="SEO Analitik"
        description="Skor trendlerini, operasyon gecmisini ve magaza capindaki iyilesme sinyallerini tek ekranda izleyin."
        eyebrow={{ label: 'Raporlar', tone: 'primary' }}
        breadcrumbs={[
          { label: 'Dashboard', to: '/' },
          { label: 'SEO Analitik' },
        ]}
        meta={[
          {
            label: 'Basari orani',
            value: `${overallSuccessRate}%`,
            tone: overallSuccessRate >= 70 ? 'success' : overallSuccessRate >= 40 ? 'warning' : 'danger',
          },
          {
            label: 'Toplam urun',
            value: summary?.total_products ?? 'Veri bekleniyor',
            tone: 'primary',
          },
        ]}
        wrapperClassName="px-5"
        actions={(
          <>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                className="rounded-md px-2 py-2 text-[11px]"
                style={{ background: 'rgba(15,23,42,0.8)', border: `1px solid ${C.border}`, color: C.text }}
              />
              <span className="text-[10px]" style={{ color: C.dimmed }}>-</span>
              <input
                type="date"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                className="rounded-md px-2 py-2 text-[11px]"
                style={{ background: 'rgba(15,23,42,0.8)', border: `1px solid ${C.border}`, color: C.text }}
              />
              <select
                value={opFilter}
                onChange={e => setOpFilter(e.target.value)}
                className="rounded-md px-2 py-2 text-[11px]"
                style={{ background: 'rgba(15,23,42,0.8)', border: `1px solid ${C.border}`, color: C.text }}
              >
                <option value="">Tum Islemler</option>
                <option value="apply">Tekil</option>
                <option value="batch_apply">Toplu</option>
                <option value="rollback">Geri Al</option>
              </select>
            </div>
            <EnterpriseButton
              tone="primary"
              onClick={() => snapshotMut.mutate()}
              disabled={snapshotMut.isPending}
              className="flex items-center gap-1.5"
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              </svg>
              {snapshotMut.isPending ? 'Kayit...' : 'Snapshot'}
            </EnterpriseButton>
          </>
        )}
      />
      {false && (
        <div className="hidden">
          <div className="flex items-center gap-1.5 mr-2">
            <input
              type="date"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
              className="px-2 py-1 rounded-md text-[10px]"
              style={{ background: 'rgba(15,23,42,0.8)', border: `1px solid ${C.border}`, color: C.text }}
            />
            <span className="text-[10px]" style={{ color: C.dimmed }}>—</span>
            <input
              type="date"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
              className="px-2 py-1 rounded-md text-[10px]"
              style={{ background: 'rgba(15,23,42,0.8)', border: `1px solid ${C.border}`, color: C.text }}
            />
            <select
              value={opFilter}
              onChange={e => setOpFilter(e.target.value)}
              className="px-2 py-1 rounded-md text-[10px]"
              style={{ background: 'rgba(15,23,42,0.8)', border: `1px solid ${C.border}`, color: C.text }}
            >
              <option value="">Tum Islemler</option>
              <option value="apply">Tekil</option>
              <option value="batch_apply">Toplu</option>
              <option value="rollback">Geri Al</option>
            </select>
          </div>

          <EnterpriseButton
            tone="primary"
            onClick={() => snapshotMut.mutate()}
            disabled={snapshotMut.isPending}
            className="flex items-center gap-1.5"
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
            </svg>
            {snapshotMut.isPending ? 'Kayit...' : 'Snapshot'}
          </EnterpriseButton>
        </div>
      )}

      {/* ── Content ──────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-auto p-5 space-y-5">

        {/* Row 1: KPI Cards */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-7">
          <KpiCard
            label="Toplam Islem"
            value={cs?.total_events ?? 0}
            sub={`${cs?.unique_products ?? 0} benzersiz urun`}
            color={C.primary}
          />
          <KpiCard
            label="Net Skor Kazanci"
            value={`${(cs?.net_change ?? 0) > 0 ? '+' : ''}${cs?.net_change ?? 0}`}
            sub={`Toplam: +${cs?.total_gain ?? 0} puan`}
            color={(cs?.net_change ?? 0) >= 0 ? C.success : C.danger}
          />
          <KpiCard
            label="Ort. Degisim"
            value={cs?.avg_delta != null ? `${cs.avg_delta > 0 ? '+' : ''}${cs.avg_delta}` : '—'}
            sub={cs?.avg_score_after != null ? `Ort. son skor: ${cs.avg_score_after}` : undefined}
            color={(cs?.avg_delta ?? 0) >= 0 ? C.success : C.danger}
          />
          <KpiCard
            label="Basari Orani"
            value={`${overallSuccessRate}%`}
            sub={`${totalImproved}/${totalOps} iyilesti`}
            color={overallSuccessRate >= 70 ? C.success : overallSuccessRate >= 40 ? C.warning : C.danger}
          />
          <KpiCard
            label="Iyilesen"
            value={cs?.improved_count ?? 0}
            sub={cs?.best_delta != null ? `En iyi: +${cs.best_delta}` : undefined}
            color={C.success}
          />
          <KpiCard
            label="Gerileyen"
            value={cs?.degraded_count ?? 0}
            sub={cs?.worst_delta != null ? `En kotu: ${cs.worst_delta}` : undefined}
            color={cs?.degraded_count ? C.danger : C.muted}
          />
          <KpiCard
            label="Urun Sayisi"
            value={summary?.total_products ?? '—'}
            sub={summary?.snapshot_count ? `${summary.snapshot_count} snapshot` : undefined}
            color={C.cyan}
          />
        </div>

        {/* Row 2: Daily + Hourly Activity Charts */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <DailyActivityChart data={dailyActivity ?? []} />
          <HourlyActivityChart data={hourlyActivity ?? []} />
        </div>

        {/* Row 3: Score Change Chart + Store Trend */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <ScoreChangeChart data={logData} />
          {trends && <StoreTrendChart data={trends} range={range} onRangeChange={setRange} />}
        </div>

        {/* Row 4: Score Distribution + Operation Metrics */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {scoreDistribution && <ScoreDistributionChart data={scoreDistribution} />}
          {operationMetrics && operationMetrics.length > 0 && <OperationMetricsCard data={operationMetrics} />}
        </div>

        {/* Row 5: Sub-score comparison + Top Improvers */}
        {summary && (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <SubScoreChart summary={summary} />
            {improvers && <TopImproversCard improvers={improvers} />}
          </div>
        )}

        {/* Row 6: Product drill-down */}
        {improvers && improvers.length > 0 && (
          <ProductDrillDown improvers={improvers} range={range} />
        )}

        {/* Row 7: Full score change log table */}
        <EnterpriseSurface className="p-0 overflow-hidden">
          <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom: `1px solid ${C.border}` }}>
            <SectionTitle>Skor Degisim Gecmisi</SectionTitle>
            {logData.length > 0 && (
              <span className="text-[10px] tabular-nums" style={{ color: C.dimmed }}>
                {logData.length} kayit
              </span>
            )}
          </div>
          <ScoreChangeTable data={logData} loading={logLoading} />
        </EnterpriseSurface>
      </main>
    </div>
  );
}

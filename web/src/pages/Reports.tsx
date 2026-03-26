import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, Cell,
} from 'recharts';
import { EnterpriseButton, EnterpriseNavButton, EnterpriseSurface } from '../shared/ui/EnterprisePrimitives';
import { useToast } from '../shared/ui/Toast';
import { getStoreTrends, getReportSummary, getTopImprovers, takeSnapshot, getProductTrends } from '../api/client';
import type { DailyStoreTrend, ReportSummary, TopImprover, DailyProductTrend } from '../types';

type DateRange = 7 | 30 | 90 | 365;

const COLORS = {
  total: '#60a5fa',
  seo: '#34d399',
  geo: '#a78bfa',
  aeo: '#fbbf24',
  grid: 'rgba(148,163,184,0.12)',
  text: 'rgba(148,163,184,0.7)',
};

const SUB_SCORE_LABELS: Record<string, string> = {
  title: 'Baslik',
  description: 'Aciklama',
  english_description: 'EN Aciklama',
  meta: 'Meta Title',
  meta_desc: 'Meta Desc',
  keyword: 'Keyword',
  content_quality: 'Icerik Kalitesi',
  technical_seo: 'Teknik SEO',
  readability: 'Okunabilirlik',
  ai_citability: 'AI Citability',
};

function formatDate(dateStr: string) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' });
}

function ImprovementBadge({ value }: { value: number }) {
  const isPositive = value > 0;
  const isZero = value === 0;
  const color = isPositive ? '#34d399' : isZero ? 'rgba(148,163,184,0.6)' : '#f87171';
  const prefix = isPositive ? '+' : '';
  return (
    <span style={{ color, fontWeight: 700, fontSize: 20 }}>
      {prefix}{value.toFixed(1)}
    </span>
  );
}

// ── Summary Cards ─────────────────────────────────────────────────────────────

function SummaryCards({ summary }: { summary: ReportSummary }) {
  if (!summary.first_date) {
    return (
      <EnterpriseSurface className="p-6 text-center" style={{ color: 'rgba(148,163,184,0.6)' }}>
        Henuz snapshot verisi yok. Urunlerinizi senkronladiktan sonra ilk snapshot otomatik olusturulacak.
      </EnterpriseSurface>
    );
  }

  const cards = [
    { label: 'Toplam Skor', key: 'total', color: COLORS.total },
    { label: 'SEO', key: 'seo', color: COLORS.seo },
    { label: 'GEO', key: 'geo', color: COLORS.geo },
    { label: 'AEO', key: 'aeo', color: COLORS.aeo },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
      {cards.map(({ label, key, color }) => (
        <EnterpriseSurface key={key} className="p-4">
          <div className="text-xs mb-1" style={{ color: 'rgba(148,163,184,0.6)' }}>{label}</div>
          <div className="flex items-baseline gap-2">
            <span style={{ color, fontSize: 24, fontWeight: 800 }}>
              {(summary.latest_avg[key] ?? 0).toFixed(1)}
            </span>
            <ImprovementBadge value={summary.improvement[key] ?? 0} />
          </div>
          <div className="text-[10px] mt-1" style={{ color: 'rgba(148,163,184,0.4)' }}>
            ilk: {(summary.first_avg[key] ?? 0).toFixed(1)}
          </div>
        </EnterpriseSurface>
      ))}

      <EnterpriseSurface className="p-4">
        <div className="text-xs mb-1" style={{ color: 'rgba(148,163,184,0.6)' }}>Urun Sayisi</div>
        <div style={{ color: '#e2e8f0', fontSize: 24, fontWeight: 800 }}>{summary.total_products}</div>
      </EnterpriseSurface>

      <EnterpriseSurface className="p-4">
        <div className="text-xs mb-1" style={{ color: 'rgba(148,163,184,0.6)' }}>Izleme Suresi</div>
        <div style={{ color: '#e2e8f0', fontSize: 24, fontWeight: 800 }}>
          {summary.snapshot_count} <span className="text-sm font-normal" style={{ color: 'rgba(148,163,184,0.5)' }}>gun</span>
        </div>
        <div className="text-[10px] mt-1" style={{ color: 'rgba(148,163,184,0.4)' }}>
          {summary.first_date} — {summary.latest_date}
        </div>
      </EnterpriseSurface>
    </div>
  );
}

// ── Store Trend Chart ─────────────────────────────────────────────────────────

function StoreTrendChart({ data, range, onRangeChange }: {
  data: DailyStoreTrend[];
  range: DateRange;
  onRangeChange: (r: DateRange) => void;
}) {
  const ranges: DateRange[] = [7, 30, 90, 365];
  const rangeLabels: Record<DateRange, string> = { 7: '7 Gun', 30: '30 Gun', 90: '90 Gun', 365: '1 Yil' };

  return (
    <EnterpriseSurface className="p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>
          Magaza Geneli Skor Trendi
        </h3>
        <div className="flex gap-1">
          {ranges.map(r => (
            <button
              key={r}
              onClick={() => onRangeChange(r)}
              className="px-2.5 py-1 rounded text-xs font-medium transition-colors"
              style={{
                background: r === range ? 'rgba(96,165,250,0.2)' : 'transparent',
                color: r === range ? '#60a5fa' : 'rgba(148,163,184,0.6)',
                border: r === range ? '1px solid rgba(96,165,250,0.3)' : '1px solid transparent',
              }}
            >
              {rangeLabels[r]}
            </button>
          ))}
        </div>
      </div>

      {data.length === 0 ? (
        <div className="h-64 flex items-center justify-center" style={{ color: 'rgba(148,163,184,0.4)' }}>
          Bu donemde veri yok
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
            <XAxis
              dataKey="snapshot_date"
              tickFormatter={formatDate}
              tick={{ fill: COLORS.text, fontSize: 11 }}
              stroke={COLORS.grid}
            />
            <YAxis domain={[0, 100]} tick={{ fill: COLORS.text, fontSize: 11 }} stroke={COLORS.grid} />
            <Tooltip
              contentStyle={{
                background: 'rgba(15,23,42,0.95)',
                border: '1px solid rgba(148,163,184,0.2)',
                borderRadius: 8,
                color: '#e2e8f0',
                fontSize: 12,
              }}
              labelFormatter={formatDate}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: COLORS.text }} />
            <Line type="monotone" dataKey="avg_total" name="Toplam" stroke={COLORS.total} strokeWidth={2.5} dot={false} />
            <Line type="monotone" dataKey="avg_seo" name="SEO" stroke={COLORS.seo} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="avg_geo" name="GEO" stroke={COLORS.geo} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="avg_aeo" name="AEO" stroke={COLORS.aeo} strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </EnterpriseSurface>
  );
}

// ── Sub-Score Comparison Chart ────────────────────────────────────────────────

function SubScoreComparisonChart({ summary }: { summary: ReportSummary }) {
  if (!summary.first_date || summary.first_date === summary.latest_date) return null;

  const data = Object.keys(SUB_SCORE_LABELS).map(key => ({
    name: SUB_SCORE_LABELS[key],
    ilk: summary.first_avg[key] ?? 0,
    son: summary.latest_avg[key] ?? 0,
  }));

  return (
    <EnterpriseSurface className="p-5">
      <h3 className="text-sm font-semibold mb-4" style={{ color: '#e2e8f0' }}>
        Alt Skor Karsilastirmasi (Ilk vs Son)
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ left: 80 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
          <XAxis type="number" tick={{ fill: COLORS.text, fontSize: 11 }} stroke={COLORS.grid} />
          <YAxis type="category" dataKey="name" tick={{ fill: COLORS.text, fontSize: 11 }} stroke={COLORS.grid} width={75} />
          <Tooltip
            contentStyle={{
              background: 'rgba(15,23,42,0.95)',
              border: '1px solid rgba(148,163,184,0.2)',
              borderRadius: 8,
              color: '#e2e8f0',
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: COLORS.text }} />
          <Bar dataKey="ilk" name="Ilk Snapshot" fill="rgba(148,163,184,0.3)" radius={[0, 4, 4, 0]} />
          <Bar dataKey="son" name="Son Snapshot" fill="#60a5fa" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </EnterpriseSurface>
  );
}

// ── Top Improvers ─────────────────────────────────────────────────────────────

function TopImproversSection({ improvers }: { improvers: TopImprover[] }) {
  if (improvers.length === 0) return null;

  return (
    <EnterpriseSurface className="p-5">
      <h3 className="text-sm font-semibold mb-4" style={{ color: '#e2e8f0' }}>
        En Cok Gelisen Urunler
      </h3>
      <div className="space-y-2">
        {improvers.map((item, i) => {
          const barPct = Math.min(Math.max(item.delta, 0), 40) / 40 * 100;
          return (
            <div key={item.product_id} className="flex items-center gap-3">
              <span className="text-xs font-bold w-5 text-right" style={{ color: 'rgba(148,163,184,0.5)' }}>
                {i + 1}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-xs truncate" style={{ color: '#e2e8f0' }}>{item.product_name}</div>
                <div className="mt-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(148,163,184,0.1)' }}>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${barPct}%`,
                      background: item.delta > 0
                        ? 'linear-gradient(90deg, #34d399, #60a5fa)'
                        : 'rgba(148,163,184,0.3)',
                    }}
                  />
                </div>
              </div>
              <div className="text-right flex items-baseline gap-1.5">
                <span className="text-[10px]" style={{ color: 'rgba(148,163,184,0.4)' }}>{item.first_score}</span>
                <span style={{ color: 'rgba(148,163,184,0.3)' }}>→</span>
                <span className="text-xs font-bold" style={{ color: '#e2e8f0' }}>{item.latest_score}</span>
                <span className="text-xs font-bold" style={{ color: item.delta > 0 ? '#34d399' : item.delta < 0 ? '#f87171' : 'rgba(148,163,184,0.5)' }}>
                  {item.delta > 0 ? '+' : ''}{item.delta}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </EnterpriseSurface>
  );
}

// ── Product Drill-Down ────────────────────────────────────────────────────────

function ProductDrillDown({ improvers, range }: { improvers: TopImprover[]; range: DateRange }) {
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null);

  const { data: productTrend } = useQuery({
    queryKey: ['product-trend', selectedProduct, range],
    queryFn: () => getProductTrends(selectedProduct!, range),
    enabled: !!selectedProduct,
  });

  if (improvers.length === 0) return null;

  return (
    <EnterpriseSurface className="p-5">
      <h3 className="text-sm font-semibold mb-3" style={{ color: '#e2e8f0' }}>
        Urun Bazli Skor Trendi
      </h3>
      <select
        value={selectedProduct ?? ''}
        onChange={e => setSelectedProduct(e.target.value || null)}
        className="w-full px-3 py-2 rounded-lg text-sm mb-4"
        style={{
          background: 'rgba(15,23,42,0.8)',
          border: '1px solid rgba(148,163,184,0.2)',
          color: '#e2e8f0',
        }}
      >
        <option value="">Urun secin...</option>
        {improvers.map(p => (
          <option key={p.product_id} value={p.product_id}>{p.product_name}</option>
        ))}
      </select>

      {selectedProduct && productTrend && productTrend.length > 0 && (
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={productTrend}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
            <XAxis
              dataKey="snapshot_date"
              tickFormatter={formatDate}
              tick={{ fill: COLORS.text, fontSize: 11 }}
              stroke={COLORS.grid}
            />
            <YAxis domain={[0, 100]} tick={{ fill: COLORS.text, fontSize: 11 }} stroke={COLORS.grid} />
            <Tooltip
              contentStyle={{
                background: 'rgba(15,23,42,0.95)',
                border: '1px solid rgba(148,163,184,0.2)',
                borderRadius: 8,
                color: '#e2e8f0',
                fontSize: 12,
              }}
              labelFormatter={formatDate}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: COLORS.text }} />
            <Line type="monotone" dataKey="total_score" name="Toplam" stroke={COLORS.total} strokeWidth={2.5} dot={false} />
            <Line type="monotone" dataKey="seo_score" name="SEO" stroke={COLORS.seo} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="geo_score" name="GEO" stroke={COLORS.geo} strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="aeo_score" name="AEO" stroke={COLORS.aeo} strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}

      {selectedProduct && productTrend && productTrend.length === 0 && (
        <div className="h-32 flex items-center justify-center text-xs" style={{ color: 'rgba(148,163,184,0.4)' }}>
          Bu urun icin veri yok
        </div>
      )}
    </EnterpriseSurface>
  );
}

// ── Issues Trend ──────────────────────────────────────────────────────────────

function IssuesTrendChart({ data }: { data: DailyStoreTrend[] }) {
  if (data.length < 2) return null;

  return (
    <EnterpriseSurface className="p-5">
      <h3 className="text-sm font-semibold mb-4" style={{ color: '#e2e8f0' }}>
        Ortalama Sorun Sayisi Trendi
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
          <XAxis
            dataKey="snapshot_date"
            tickFormatter={formatDate}
            tick={{ fill: COLORS.text, fontSize: 11 }}
            stroke={COLORS.grid}
          />
          <YAxis tick={{ fill: COLORS.text, fontSize: 11 }} stroke={COLORS.grid} />
          <Tooltip
            contentStyle={{
              background: 'rgba(15,23,42,0.95)',
              border: '1px solid rgba(148,163,184,0.2)',
              borderRadius: 8,
              color: '#e2e8f0',
              fontSize: 12,
            }}
            labelFormatter={formatDate}
          />
          <Line type="monotone" dataKey="avg_issues" name="Ort. Sorun" stroke="#f87171" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </EnterpriseSurface>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Reports() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [range, setRange] = useState<DateRange>(90);

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['report-summary'],
    queryFn: getReportSummary,
  });

  const { data: trends, isLoading: trendsLoading } = useQuery({
    queryKey: ['store-trends', range],
    queryFn: () => getStoreTrends(range),
  });

  const { data: improvers } = useQuery({
    queryKey: ['top-improvers'],
    queryFn: () => getTopImprovers(15),
  });

  const snapshotMutation = useMutation({
    mutationFn: takeSnapshot,
    onSuccess: () => {
      toast.success('Snapshot basariyla olusturuldu');
      queryClient.invalidateQueries({ queryKey: ['report-summary'] });
      queryClient.invalidateQueries({ queryKey: ['store-trends'] });
      queryClient.invalidateQueries({ queryKey: ['top-improvers'] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const isLoading = summaryLoading || trendsLoading;

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base, #020617)' }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-5 py-3"
        style={{
          background: 'linear-gradient(180deg, rgba(2,6,23,0.95), rgba(15,23,42,0.9))',
          borderBottom: '1px solid rgba(148,163,184,0.16)',
        }}
      >
        <div className="flex items-center gap-3">
          <Link to="/">
            <EnterpriseNavButton>
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Dashboard
            </EnterpriseNavButton>
          </Link>
          <div className="h-5 w-px" style={{ background: 'rgba(148,163,184,0.16)' }} />
          <h1 className="text-[15px] font-semibold tracking-tight" style={{ color: '#e2e8f0' }}>
            SEO/GEO Skor Takibi
          </h1>
        </div>

        <EnterpriseButton
          tone="primary"
          onClick={() => snapshotMutation.mutate()}
          disabled={snapshotMutation.isPending}
          className="flex items-center gap-1.5"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {snapshotMutation.isPending ? 'Olusturuluyor...' : 'Snapshot Al'}
        </EnterpriseButton>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-auto p-5 space-y-5">
        {isLoading ? (
          <div className="flex h-64 items-center justify-center" style={{ color: 'rgba(148,163,184,0.5)' }}>
            Yukleniyor...
          </div>
        ) : (
          <>
            {summary && <SummaryCards summary={summary} />}

            {trends && <StoreTrendChart data={trends} range={range} onRangeChange={setRange} />}

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              {summary && <SubScoreComparisonChart summary={summary} />}
              {improvers && <TopImproversSection improvers={improvers} />}
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              {trends && <IssuesTrendChart data={trends} />}
              {improvers && <ProductDrillDown improvers={improvers} range={range} />}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

import type {
  StoreOrderEntry,
  StoreOrderMessageData,
  StoreOrderMetric,
} from './storeOrderMessageParser';
import { normalizeStoreText } from './storeOrderMessageParser';

const KIND_META: Record<StoreOrderMessageData['kind'], {
  eyebrow: string;
  accent: string;
  border: string;
  glow: string;
  subtitle: string;
}> = {
  recent_orders: {
    eyebrow: 'Siparis Akisi',
    accent: '#7dd3fc',
    border: 'rgba(125, 211, 252, 0.18)',
    glow: 'rgba(56, 189, 248, 0.22)',
    subtitle: 'En yeni siparisler canli ikas verisiyle kartlara ayrildi.',
  },
  pending_orders: {
    eyebrow: 'Takip Listesi',
    accent: '#fbbf24',
    border: 'rgba(251, 191, 36, 0.18)',
    glow: 'rgba(245, 158, 11, 0.22)',
    subtitle: 'Bekleyen odeme ve taslak siparisler one cikarildi.',
  },
  today_summary: {
    eyebrow: 'Gunluk Ozet',
    accent: '#34d399',
    border: 'rgba(52, 211, 153, 0.18)',
    glow: 'rgba(16, 185, 129, 0.22)',
    subtitle: 'Bugune ait siparis sinyalleri tek bir gorunumde toplandi.',
  },
};

const STATUS_LABELS: Record<string, string> = {
  CREATED: 'Olustu',
  PAID: 'Odendi',
  WAITING: 'Bekliyor',
  PENDING: 'Bekliyor',
  UNPAID: 'Odenmedi',
  NOT_PAID: 'Odenmedi',
  DRAFT: 'Taslak',
  CANCELLED: 'Iptal',
  REFUNDED: 'Iade',
  PARTIALLY_CANCELLED: 'Kismi iptal',
  PARTIALLY_REFUNDED: 'Kismi iade',
  WAITING_UPSELL_ACTION: 'Aksiyon bekliyor',
};

const COUNT_FORMATTER = new Intl.NumberFormat('tr-TR');
const DECIMAL_FORMATTER = new Intl.NumberFormat('tr-TR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

type Tone = 'info' | 'success' | 'warning' | 'danger' | 'neutral';

function parseLooseNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed || trimmed === '-') {
    return null;
  }

  if (/^-?\d+(?:\.\d+)?$/.test(trimmed)) {
    return Number(trimmed);
  }

  if (/^-?\d+(?:,\d+)?$/.test(trimmed)) {
    return Number(trimmed.replace(',', '.'));
  }

  return null;
}

function formatCount(value: string): string {
  const parsed = parseLooseNumber(value);
  if (parsed === null) {
    return value;
  }
  return COUNT_FORMATTER.format(parsed);
}

function formatMoney(value: string): string {
  const parsed = parseLooseNumber(value);
  if (parsed === null) {
    return value;
  }
  return DECIMAL_FORMATTER.format(parsed);
}

function prettifyStatus(value: string): string {
  const normalized = value.trim().toUpperCase();
  if (STATUS_LABELS[normalized]) {
    return STATUS_LABELS[normalized];
  }

  return value
    .trim()
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function toneStyles(tone: Tone): { background: string; border: string; text: string } {
  switch (tone) {
    case 'info':
      return {
        background: 'rgba(59, 130, 246, 0.14)',
        border: 'rgba(96, 165, 250, 0.22)',
        text: '#bfdbfe',
      };
    case 'success':
      return {
        background: 'rgba(16, 185, 129, 0.14)',
        border: 'rgba(52, 211, 153, 0.22)',
        text: '#bbf7d0',
      };
    case 'warning':
      return {
        background: 'rgba(245, 158, 11, 0.14)',
        border: 'rgba(251, 191, 36, 0.22)',
        text: '#fde68a',
      };
    case 'danger':
      return {
        background: 'rgba(239, 68, 68, 0.14)',
        border: 'rgba(248, 113, 113, 0.22)',
        text: '#fecaca',
      };
    default:
      return {
        background: 'rgba(148, 163, 184, 0.12)',
        border: 'rgba(148, 163, 184, 0.18)',
        text: '#cbd5e1',
      };
  }
}

function getStatusTone(value: string, type: 'status' | 'payment'): Tone {
  const normalized = value.trim().toUpperCase();

  if (type === 'payment') {
    if (normalized === 'PAID') {
      return 'success';
    }
    if (normalized === 'WAITING' || normalized === 'PENDING' || normalized === 'UNPAID' || normalized === 'NOT_PAID') {
      return 'warning';
    }
    if (normalized === 'REFUNDED' || normalized === 'CANCELLED' || normalized === 'PARTIALLY_REFUNDED') {
      return 'danger';
    }
    return 'neutral';
  }

  if (normalized === 'CREATED') {
    return 'info';
  }
  if (normalized === 'WAITING' || normalized === 'PENDING' || normalized === 'DRAFT' || normalized === 'WAITING_UPSELL_ACTION') {
    return 'warning';
  }
  if (normalized === 'CANCELLED' || normalized === 'REFUNDED' || normalized === 'PARTIALLY_CANCELLED' || normalized === 'PARTIALLY_REFUNDED') {
    return 'danger';
  }
  return 'neutral';
}

function getMetricTone(label: string): Tone {
  const normalized = normalizeStoreText(label);

  if (normalized === 'toplam ciro') {
    return 'info';
  }
  if (normalized === 'odemesi tamamlanan') {
    return 'success';
  }
  if (normalized === 'bekleyen' || normalized === 'bekleyen siparis') {
    return 'warning';
  }
  if (normalized === 'iptal/iade') {
    return 'danger';
  }
  return 'neutral';
}

function formatMetricValue(metric: StoreOrderMetric): string {
  const normalized = normalizeStoreText(metric.label);
  if (normalized === 'tarih') {
    return metric.value;
  }
  if (normalized === 'toplam ciro') {
    return formatMoney(metric.value);
  }
  return formatCount(metric.value);
}

function buildDisplayMetrics(data: StoreOrderMessageData): StoreOrderMetric[] {
  const metrics: StoreOrderMetric[] = [];

  for (const metric of data.metrics) {
    const normalized = normalizeStoreText(metric.label);
    const countValue = parseLooseNumber(metric.value);

    if (
      (normalized === 'gosterilen siparis' || normalized === 'bekleyen siparis')
      && countValue !== null
      && countValue > data.orders.length
      && data.orders.length > 0
    ) {
      metrics.push({
        label: normalized === 'gosterilen siparis' ? 'Toplam siparis' : 'Bekleyen toplam',
        value: metric.value,
      });
      metrics.push({
        label: 'Kartta gosterilen',
        value: String(data.orders.length),
      });
      continue;
    }

    metrics.push(metric);
  }

  if (metrics.length === 0 && data.orders.length > 0) {
    metrics.push({
      label: 'Kartta gosterilen',
      value: String(data.orders.length),
    });
  }

  return metrics;
}

function StatChip({ metric }: { metric: StoreOrderMetric }) {
  const tone = toneStyles(getMetricTone(metric.label));

  return (
    <div
      className="rounded-2xl border px-3 py-2.5"
      style={{
        background: tone.background,
        borderColor: tone.border,
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)',
      }}
    >
      <div
        className="text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'rgba(226, 232, 240, 0.56)' }}
      >
        {metric.label}
      </div>
      <div className="mt-1 text-sm font-semibold" style={{ color: tone.text }}>
        {formatMetricValue(metric)}
      </div>
    </div>
  );
}

function StatusPill({
  label,
  value,
  type,
}: {
  label: string;
  value: string;
  type: 'status' | 'payment';
}) {
  const tone = toneStyles(getStatusTone(value, type));

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium"
      style={{
        background: tone.background,
        borderColor: tone.border,
        color: tone.text,
      }}
    >
      <span className="opacity-70">{label}</span>
      <span>{prettifyStatus(value)}</span>
    </span>
  );
}

function OrderTotal({ totalText }: { totalText: string }) {
  return (
    <div
      className="rounded-2xl border px-3 py-2"
      style={{
        background: 'linear-gradient(180deg, rgba(15, 23, 42, 0.86), rgba(15, 23, 42, 0.56))',
        borderColor: 'rgba(148, 163, 184, 0.16)',
      }}
    >
      <div
        className="text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'rgba(148, 163, 184, 0.78)' }}
      >
        Toplam
      </div>
      <div className="mt-1 text-base font-semibold text-white">{formatMoney(totalText)}</div>
    </div>
  );
}

function OrderItems({ order }: { order: StoreOrderEntry }) {
  if (order.items.length === 0 && !order.extraItemsText) {
    return <span style={{ color: 'var(--color-text-secondary)' }}>Urun bilgisi yok</span>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {order.items.map((item) => (
        <span
          key={item}
          className="rounded-full border px-2.5 py-1 text-[11px]"
          style={{
            background: 'rgba(255,255,255,0.04)',
            borderColor: 'rgba(148, 163, 184, 0.16)',
            color: 'var(--color-text-primary)',
          }}
        >
          {item}
        </span>
      ))}
      {order.extraItemsText ? (
        <span
          className="rounded-full border px-2.5 py-1 text-[11px] font-medium"
          style={{
            background: 'rgba(125, 211, 252, 0.12)',
            borderColor: 'rgba(125, 211, 252, 0.2)',
            color: '#bae6fd',
          }}
        >
          {order.extraItemsText}
        </span>
      ) : null}
    </div>
  );
}

function OrderCard({ order }: { order: StoreOrderEntry }) {
  return (
    <article
      className="rounded-[20px] border p-4 transition-transform duration-200 hover:-translate-y-0.5"
      style={{
        background: 'linear-gradient(180deg, rgba(255,255,255,0.035), rgba(15,23,42,0.32))',
        borderColor: 'rgba(148, 163, 184, 0.16)',
        boxShadow: '0 14px 32px rgba(2, 6, 23, 0.22)',
      }}
      aria-label={`Siparis ${order.orderNumber}`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold"
              style={{
                background: 'rgba(255,255,255,0.05)',
                borderColor: 'rgba(148, 163, 184, 0.16)',
                color: '#e2e8f0',
              }}
            >
              #{order.orderNumber}
            </span>
            <span className="text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
              {order.orderedAt}
            </span>
          </div>

          <div className="mt-2 flex flex-wrap gap-2">
            <StatusPill label="Durum" value={order.status} type="status" />
            <StatusPill label="Odeme" value={order.paymentStatus} type="payment" />
          </div>
        </div>

        <OrderTotal totalText={order.totalText} />
      </div>

      <div className="mt-3 grid gap-3">
        <div
          className="flex items-start gap-2 rounded-2xl border px-3 py-2.5"
          style={{
            background: 'rgba(15, 23, 42, 0.42)',
            borderColor: 'rgba(148, 163, 184, 0.12)',
          }}
        >
          <svg
            className="mt-0.5 h-3.5 w-3.5 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            style={{ color: 'rgba(148, 163, 184, 0.82)' }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5.121 17.804A9 9 0 1118.36 4.566M15 11a3 3 0 11-6 0 3 3 0 016 0zM19 20l-4.35-4.35" />
          </svg>
          <div className="min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'rgba(148, 163, 184, 0.7)' }}>
              Musteri
            </div>
            <div className="mt-1 break-words text-[13px] text-white">
              {order.customer === '-' ? 'Musteri bilgisi yok' : order.customer}
            </div>
          </div>
        </div>

        <div
          className="rounded-2xl border px-3 py-2.5"
          style={{
            background: 'rgba(15, 23, 42, 0.42)',
            borderColor: 'rgba(148, 163, 184, 0.12)',
          }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'rgba(148, 163, 184, 0.7)' }}>
            Urunler
          </div>
          <div className="mt-2">
            <OrderItems order={order} />
          </div>
        </div>
      </div>
    </article>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="px-4 pb-4">
      <div
        className="rounded-[20px] border border-dashed px-4 py-6 text-center"
        style={{
          background: 'rgba(15, 23, 42, 0.34)',
          borderColor: 'rgba(148, 163, 184, 0.18)',
        }}
      >
        <div className="text-sm font-semibold text-white">{message}</div>
        <div className="mt-1 text-[12px]" style={{ color: 'var(--color-text-secondary)' }}>
          Yeni siparisler geldiginde bu alan ozet kartlariyla dolacak.
        </div>
      </div>
    </div>
  );
}

export default function StoreOrderMessage({ data }: { data: StoreOrderMessageData }) {
  const meta = KIND_META[data.kind];
  const metrics = buildDisplayMetrics(data);

  return (
    <section
      className="relative overflow-hidden rounded-[24px] border"
      style={{
        background: 'linear-gradient(180deg, rgba(8, 47, 73, 0.2), rgba(15, 23, 42, 0.94))',
        borderColor: meta.border,
        boxShadow: '0 22px 60px rgba(2, 6, 23, 0.38)',
      }}
    >
      <div
        className="pointer-events-none absolute -left-8 top-0 h-28 w-28 rounded-full blur-3xl"
        style={{ background: meta.glow }}
      />
      <div
        className="pointer-events-none absolute right-0 top-8 h-32 w-32 rounded-full blur-3xl"
        style={{ background: meta.glow }}
      />

      <div className="relative">
        <div
          className="border-b px-4 py-4"
          style={{ borderColor: 'rgba(148, 163, 184, 0.14)' }}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <div
                className="flex h-11 w-11 items-center justify-center rounded-2xl border"
                style={{
                  background: 'rgba(15, 23, 42, 0.56)',
                  borderColor: meta.border,
                  color: meta.accent,
                }}
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10m-9 4h6m4 6H6a2 2 0 01-2-2V7a2 2 0 012-2h1m10 0h1a2 2 0 012 2v12a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <div
                  className="text-[10px] font-semibold uppercase tracking-[0.2em]"
                  style={{ color: meta.accent }}
                >
                  {meta.eyebrow}
                </div>
                <h3 className="mt-1 text-[18px] font-semibold tracking-tight text-white">{data.title}</h3>
                <p className="mt-1 max-w-xl text-[12px]" style={{ color: 'rgba(226, 232, 240, 0.72)' }}>
                  {meta.subtitle}
                </p>
              </div>
            </div>

            <div
              className="inline-flex items-center gap-2 self-start rounded-full border px-3 py-1.5 text-[11px] font-medium"
              style={{
                background: 'rgba(15, 23, 42, 0.58)',
                borderColor: meta.border,
                color: 'rgba(226, 232, 240, 0.82)',
              }}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: meta.accent, boxShadow: `0 0 0 6px ${meta.glow}` }}
              />
              Canli ikas MCP verisi
            </div>
          </div>
        </div>

        {metrics.length > 0 ? (
          <div
            className="grid gap-2 border-b px-4 py-3 sm:grid-cols-2 xl:grid-cols-4"
            style={{ borderColor: 'rgba(148, 163, 184, 0.12)' }}
          >
            {metrics.map((metric) => (
              <StatChip key={`${metric.label}-${metric.value}`} metric={metric} />
            ))}
          </div>
        ) : null}

        {data.emptyMessage ? <EmptyState message={data.emptyMessage} /> : null}

        {data.orders.length > 0 ? (
          <div className="space-y-3 px-4 py-4">
            {data.orders.map((order) => (
              <OrderCard key={`${order.orderNumber}-${order.orderedAt}`} order={order} />
            ))}
          </div>
        ) : null}

        {data.note ? (
          <div
            className="border-t px-4 py-3"
            style={{ borderColor: 'rgba(148, 163, 184, 0.12)' }}
          >
            <div
              className="rounded-2xl border px-3 py-2.5 text-[12px]"
              style={{
                background: 'rgba(255,255,255,0.03)',
                borderColor: 'rgba(148, 163, 184, 0.12)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {data.note}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

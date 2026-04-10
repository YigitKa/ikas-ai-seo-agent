export type StoreOrderMessageKind = 'recent_orders' | 'pending_orders' | 'today_summary';

export interface StoreOrderMetric {
  label: string;
  value: string;
}

export interface StoreOrderEntry {
  orderNumber: string;
  orderedAt: string;
  status: string;
  paymentStatus: string;
  totalText: string;
  customer: string;
  items: string[];
  extraItemsText?: string;
}

export interface StoreOrderMessageData {
  kind: StoreOrderMessageKind;
  title: string;
  metrics: StoreOrderMetric[];
  orders: StoreOrderEntry[];
  note?: string;
  emptyMessage?: string;
}

const TITLE_MAP: Record<string, { kind: StoreOrderMessageKind; title: string }> = {
  'son siparisler': { kind: 'recent_orders', title: 'Son Siparisler' },
  'bekleyen siparisler': { kind: 'pending_orders', title: 'Bekleyen Siparisler' },
  'bugunun satis ozeti': { kind: 'today_summary', title: 'Bugunun Satis Ozeti' },
};

const ORDER_LINE_PATTERN = /^- #([^|]+)\|\s*([^|]+)\|\s*durum:\s*([^|]+)\|\s*odeme:\s*([^|]+)\|\s*toplam:\s*([^|]+)\|\s*musteri:\s*([^|]+)\|\s*urunler:\s*(.+)$/i;
const EXTRA_ITEMS_PATTERN = /^\+\d+\s+urun\s+daha$/i;

export function normalizeStoreText(value: string): string {
  return value
    .replace(/[\u00c7\u00e7\u011e\u011f\u0130\u0131\u00d6\u00f6\u015e\u015f\u00dc\u00fc]/g, (char) => {
      switch (char) {
        case '\u00c7':
        case '\u00e7':
          return 'c';
        case '\u011e':
        case '\u011f':
          return 'g';
        case '\u0130':
        case '\u0131':
          return 'i';
        case '\u00d6':
        case '\u00f6':
          return 'o';
        case '\u015e':
        case '\u015f':
          return 's';
        case '\u00dc':
        case '\u00fc':
          return 'u';
        default:
          return char;
      }
    })
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function stripMarkdownWrapper(value: string): string {
  return value.replace(/^\*+|\*+$/g, '').trim();
}

function parseOrderItems(itemSummary: string): { items: string[]; extraItemsText?: string } {
  const parts = itemSummary
    .split(/\s*,\s*/)
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length === 0) {
    return { items: [] };
  }

  const lastPart = parts[parts.length - 1];
  if (EXTRA_ITEMS_PATTERN.test(lastPart)) {
    return {
      items: parts.slice(0, -1),
      extraItemsText: lastPart,
    };
  }

  return { items: parts };
}

export function parseStoreOrderMessage(content: string): StoreOrderMessageData | null {
  const lines = content.replace(/\r/g, '').split('\n');
  const firstContentLine = lines.find((line) => line.trim().length > 0);
  if (!firstContentLine) {
    return null;
  }

  const normalizedTitle = normalizeStoreText(stripMarkdownWrapper(firstContentLine));
  const titleMeta = TITLE_MAP[normalizedTitle];
  if (!titleMeta) {
    return null;
  }

  const metrics: StoreOrderMetric[] = [];
  const orders: StoreOrderEntry[] = [];
  const noteLines: string[] = [];
  let emptyMessage: string | undefined;
  let section: 'body' | 'note' = 'body';

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line === firstContentLine.trim()) {
      continue;
    }

    const maybeSectionHeading = stripMarkdownWrapper(line);
    if (normalizeStoreText(maybeSectionHeading) === 'not') {
      section = 'note';
      continue;
    }

    if (section === 'note') {
      noteLines.push(line.startsWith('- ') ? line.slice(2).trim() : line);
      continue;
    }

    const orderMatch = line.match(ORDER_LINE_PATTERN);
    if (orderMatch) {
      const [, orderNumber, orderedAt, status, paymentStatus, totalText, customer, itemSummary] = orderMatch;
      const { items, extraItemsText } = parseOrderItems(itemSummary.trim());
      orders.push({
        orderNumber: orderNumber.trim(),
        orderedAt: orderedAt.trim(),
        status: status.trim(),
        paymentStatus: paymentStatus.trim(),
        totalText: totalText.trim(),
        customer: customer.trim(),
        items,
        extraItemsText,
      });
      continue;
    }

    if (!line.startsWith('- ')) {
      continue;
    }

    const text = line.slice(2).trim();
    const metricMatch = text.match(/^([^:]+):\s*(.+)$/);
    if (metricMatch) {
      metrics.push({
        label: metricMatch[1].trim(),
        value: metricMatch[2].trim(),
      });
      continue;
    }

    emptyMessage = text;
  }

  if (!metrics.length && !orders.length && !noteLines.length && !emptyMessage) {
    return null;
  }

  return {
    kind: titleMeta.kind,
    title: titleMeta.title,
    metrics,
    orders,
    note: noteLines.join(' ').trim() || undefined,
    emptyMessage,
  };
}

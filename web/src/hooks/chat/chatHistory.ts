import type { ChatMessage } from './chatMessageModel';

const KEY_PREFIX = 'ikas_chat_';
const MAX_MESSAGES = 200;

function historyKey(productId: string): string {
  return `${KEY_PREFIX}${productId}`;
}

function unreadKey(productId: string): string {
  return `${KEY_PREFIX}${productId}_unread`;
}

/** Load stored chat messages for a product. Returns empty array if none. */
export function loadHistory(productId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(historyKey(productId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

/** Persist chat messages for a product (last MAX_MESSAGES kept). */
export function saveHistory(productId: string, messages: ChatMessage[]): void {
  if (!messages.length) return;
  try {
    // Strip transient pendingSuggestion to avoid storing stale suggestion objects
    const serializable = messages.map((message) => {
      const next = { ...message };
      delete next.pendingSuggestion;
      return next;
    });
    const slice = serializable.slice(-MAX_MESSAGES);
    localStorage.setItem(historyKey(productId), JSON.stringify(slice));
  } catch {
    // localStorage may be full or unavailable – silently skip
  }
}

/** Remove stored history and unread flag for a product. */
export function clearHistory(productId: string): void {
  localStorage.removeItem(historyKey(productId));
  localStorage.removeItem(unreadKey(productId));
}

/** Returns true if there are stored messages for the product. */
export function hasHistory(productId: string): boolean {
  try {
    const raw = localStorage.getItem(historyKey(productId));
    if (!raw) return false;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length > 0;
  } catch {
    return false;
  }
}

/** Returns true if the product has unseen background messages. */
export function isUnread(productId: string): boolean {
  return localStorage.getItem(unreadKey(productId)) === '1';
}

export function markUnread(productId: string): void {
  localStorage.setItem(unreadKey(productId), '1');
}

export function markRead(productId: string): void {
  localStorage.removeItem(unreadKey(productId));
}

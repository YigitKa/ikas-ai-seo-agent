import { createContext, useCallback, useContext, useRef, useState } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────────

export type ToastTone = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastContextValue {
  show: (message: string, tone?: ToastTone) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null);

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}

// ── Style helpers ─────────────────────────────────────────────────────────────

function toneStyles(tone: ToastTone): { border: string; iconColor: string; icon: string } {
  switch (tone) {
    case 'success':
      return {
        border: 'rgba(16, 185, 129, 0.35)',
        iconColor: '#34d399',
        icon: 'M5 13l4 4L19 7',
      };
    case 'error':
      return {
        border: 'rgba(239, 68, 68, 0.35)',
        iconColor: '#f87171',
        icon: 'M6 18L18 6M6 6l12 12',
      };
    case 'warning':
      return {
        border: 'rgba(245, 158, 11, 0.35)',
        iconColor: '#fbbf24',
        icon: 'M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z',
      };
    case 'info':
    default:
      return {
        border: 'rgba(99, 102, 241, 0.35)',
        iconColor: '#818cf8',
        icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
      };
  }
}

// ── Single Toast Item ─────────────────────────────────────────────────────────

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  const style = toneStyles(toast.tone);

  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-[13px] shadow-lg"
      style={{
        background: 'rgba(17, 17, 24, 0.96)',
        border: `1px solid ${style.border}`,
        color: 'var(--color-text-primary)',
        backdropFilter: 'blur(12px)',
        minWidth: '260px',
        maxWidth: '380px',
        animation: 'toast-in 0.22s cubic-bezier(0.22,1,0.36,1) both',
      }}
    >
      <svg
        className="mt-0.5 h-4 w-4 flex-shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        style={{ color: style.iconColor }}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d={style.icon} />
      </svg>
      <span className="flex-1 leading-snug">{toast.message}</span>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        className="mt-0.5 rounded p-0.5 transition-opacity hover:opacity-60"
        style={{ color: 'var(--color-text-muted)' }}
        aria-label="Kapat"
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

// ── Provider ──────────────────────────────────────────────────────────────────

const AUTO_DISMISS_MS = 4000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counterRef = useRef(0);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  const show = useCallback(
    (message: string, tone: ToastTone = 'info') => {
      const id = ++counterRef.current;
      setToasts((prev) => [...prev, { id, tone, message }]);
      const timer = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
      timersRef.current.set(id, timer);
    },
    [dismiss],
  );

  const success = useCallback((msg: string) => show(msg, 'success'), [show]);
  const error = useCallback((msg: string) => show(msg, 'error'), [show]);
  const info = useCallback((msg: string) => show(msg, 'info'), [show]);
  const warning = useCallback((msg: string) => show(msg, 'warning'), [show]);

  return (
    <ToastContext.Provider value={{ show, success, error, info, warning }}>
      {children}
      {/* Toast container — fixed bottom-right, above everything */}
      {toasts.length > 0 && (
        <div
          className="pointer-events-none fixed bottom-5 right-5 z-50 flex flex-col items-end gap-2"
          aria-live="polite"
          aria-atomic="false"
        >
          {toasts.map((t) => (
            <div key={t.id} className="pointer-events-auto">
              <ToastItem toast={t} onDismiss={dismiss} />
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}

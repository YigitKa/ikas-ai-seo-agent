import type { CSSProperties, ReactNode } from 'react';

function classNames(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ');
}

const TONE_STYLES: Record<'neutral' | 'primary' | 'success' | 'warning' | 'danger', CSSProperties> = {
  neutral: {
    background: 'rgba(15, 23, 42, 0.72)',
    border: '1px solid rgba(148,163,184,0.24)',
    color: 'var(--color-text-secondary)',
  },
  primary: {
    background: 'linear-gradient(135deg, rgba(99,102,241,0.34), rgba(59,130,246,0.2))',
    border: '1px solid rgba(99,102,241,0.42)',
    color: '#e0e7ff',
  },
  success: {
    background: 'rgba(16,185,129,0.16)',
    border: '1px solid rgba(16,185,129,0.35)',
    color: '#a7f3d0',
  },
  warning: {
    background: 'rgba(245,158,11,0.14)',
    border: '1px solid rgba(245,158,11,0.35)',
    color: '#fde68a',
  },
  danger: {
    background: 'rgba(239,68,68,0.12)',
    border: '1px solid rgba(239,68,68,0.35)',
    color: '#fecaca',
  },
};

export function EnterpriseSurface({
  children,
  className,
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <section
      className={classNames('enterprise-surface rounded-2xl', className)}
      style={style}
    >
      {children}
    </section>
  );
}

export function EnterpriseButton({
  children,
  onClick,
  disabled,
  tone = 'neutral',
  className,
  type = 'button',
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger';
  className?: string;
  type?: 'button' | 'submit';
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={classNames(
        'rounded-xl px-3.5 py-2 text-[13px] font-medium transition-all duration-200 hover:-translate-y-0.5 hover:brightness-110 disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40',
        className,
      )}
      style={TONE_STYLES[tone]}
    >
      {children}
    </button>
  );
}

export function EnterpriseInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className={classNames(
        'enterprise-input w-full rounded-xl py-2.5 pl-9 pr-8 text-xs outline-none transition duration-200 placeholder:text-[var(--color-text-muted)]',
        className,
      )}
    />
  );
}

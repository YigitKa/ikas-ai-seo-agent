import type { CSSProperties, ReactNode } from 'react';

function classNames(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ');
}

const TONE_STYLES: Record<'neutral' | 'primary' | 'success' | 'warning' | 'danger', CSSProperties> = {
  neutral: {
    background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.78), rgba(30, 41, 59, 0.62))',
    border: '1px solid rgba(148,163,184,0.24)',
    color: 'var(--color-text-secondary)',
  },
  primary: {
    background: 'linear-gradient(135deg, rgba(37,99,235,0.48), rgba(79,70,229,0.38))',
    border: '1px solid rgba(96,165,250,0.42)',
    color: '#e2e8f0',
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
  size = 'md',
  fullWidth = false,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger';
  className?: string;
  type?: 'button' | 'submit';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
}) {
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-3.5 py-2 text-[13px]',
    lg: 'h-11 px-4 text-sm',
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={classNames(
        'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 hover:-translate-y-0.5 hover:brightness-110 disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40',
        sizeClasses[size],
        fullWidth && 'w-full',
        className,
      )}
      style={TONE_STYLES[tone]}
    >
      {children}
    </button>
  );
}

export function EnterpriseNavButton({
  children,
  active = false,
  className,
}: {
  children: ReactNode;
  active?: boolean;
  className?: string;
}) {
  return (
    <span
      className={classNames(
        'inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-[13px] font-medium transition-all duration-200 hover:-translate-y-0.5',
        className,
      )}
      style={{
        color: active ? '#e2e8f0' : 'var(--color-text-secondary)',
        background: active
          ? 'linear-gradient(135deg, rgba(30,64,175,0.54), rgba(67,56,202,0.54))'
          : 'rgba(15, 23, 42, 0.52)',
        border: active ? '1px solid rgba(125,211,252,0.34)' : '1px solid rgba(148,163,184,0.22)',
        boxShadow: active ? '0 12px 28px rgba(30,64,175,0.28)' : 'none',
      }}
    >
      {children}
    </span>
  );
}

export function EnterprisePill({
  children,
  className,
  tone = 'neutral',
}: {
  children: ReactNode;
  className?: string;
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'primary';
}) {
  const toneStyleMap: Record<string, CSSProperties> = {
    neutral: {
      background: 'rgba(15, 23, 42, 0.76)',
      border: '1px solid rgba(148, 163, 184, 0.22)',
      color: 'var(--color-text-secondary)',
    },
    primary: TONE_STYLES.primary,
    success: TONE_STYLES.success,
    warning: TONE_STYLES.warning,
    danger: TONE_STYLES.danger,
  };
  return (
    <span
      className={classNames('inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em]', className)}
      style={toneStyleMap[tone]}
    >
      {children}
    </span>
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

// ── Settings-grade form primitives ────────────────────────────────────────

export function EnterpriseField({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  hint,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="enterprise-field rounded-xl placeholder:text-[color:var(--color-text-muted)]"
      />
      {hint && (
        <span className="mt-1.5 block text-xs leading-5" style={{ color: 'var(--color-text-muted)' }}>
          {hint}
        </span>
      )}
    </label>
  );
}

export function EnterpriseSelectField({
  label,
  value,
  onChange,
  options,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="enterprise-field rounded-xl"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint && (
        <span className="mt-1.5 block text-xs leading-5" style={{ color: 'var(--color-text-muted)' }}>
          {hint}
        </span>
      )}
    </label>
  );
}

export function EnterpriseToggleField({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="enterprise-list-item flex cursor-pointer items-start gap-4 rounded-xl p-4 transition-all duration-200">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded"
        style={{ accentColor: 'var(--color-primary)' }}
      />
      <span className="block">
        <span className="block text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
          {title}
        </span>
        <span className="mt-1 block text-xs leading-5" style={{ color: 'var(--color-text-secondary)' }}>
          {description}
        </span>
      </span>
    </label>
  );
}

export function EnterpriseSectionCard({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="enterprise-surface rounded-2xl p-5 sm:p-6">
      <div
        className="mb-5 flex flex-col gap-4 pb-5 md:flex-row md:items-end md:justify-between"
        style={{ borderBottom: '1px solid rgba(148,163,184,0.14)' }}
      >
        <div>
          <div
            className="text-[11px] font-semibold uppercase tracking-[0.24em]"
            style={{ color: 'var(--color-accent-light)' }}
          >
            {eyebrow}
          </div>
          <h2 className="mt-2 text-[17px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {title}
          </h2>
          <p className="mt-2 max-w-3xl text-[13px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
            {description}
          </p>
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function EnterpriseBanner({
  tone,
  message,
  className = '',
}: {
  tone: 'success' | 'error' | 'info';
  message: string;
  className?: string;
}) {
  const styleMap: Record<string, CSSProperties> = {
    success: TONE_STYLES.success,
    error: TONE_STYLES.danger,
    info: TONE_STYLES.primary,
  };
  return (
    <div className={classNames('rounded-xl px-4 py-3 text-[13px]', className)} style={styleMap[tone]}>
      {message}
    </div>
  );
}

export function EnterpriseStatusRow({
  label,
  value,
  mono = true,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div
      className="flex items-start justify-between gap-3 pb-4 last:pb-0"
      style={{ borderBottom: '1px solid rgba(148,163,184,0.1)' }}
    >
      <dt className="text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
        {label}
      </dt>
      <dd
        className={classNames('max-w-[60%] text-right text-[13px]', mono ? 'font-mono text-xs' : '')}
        style={{ color: 'var(--color-text-primary)' }}
      >
        {value}
      </dd>
    </div>
  );
}

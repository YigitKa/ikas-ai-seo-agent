import { useEffect, useState, type ReactNode } from 'react';
import {
  Link,
  useLocation,
  useNavigate,
  useNavigationType,
} from 'react-router-dom';
import { EnterpriseNavButton, EnterprisePill } from './EnterprisePrimitives';
import ThemeToggle from '../../theme/ThemeToggle';
import { themeColors } from '../../theme/colors';

function classNames(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ');
}

const NAV_ITEMS = [
  { to: '/', label: 'Komuta Merkezi', icon: 'M3 10.5L12 3l9 7.5M5.25 9.75v9.75h13.5V9.75' },
  { to: '/workspace', label: 'Calisma Alani', icon: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' },
  { to: '/reports', label: 'Raporlar', icon: 'M5 12h3m4-6h3m4 12h3M7 6v12m7-6v6m7-12v12' },
  { to: '/batch', label: 'Toplu Islem', icon: 'M4 6h16M4 12h16M4 18h16' },
  { to: '/diagnostics', label: 'Diagnostics', icon: 'M9 12l2 2 4-4m5-2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { to: '/llms', label: 'llms Studio', icon: 'M4 7h16M4 12h10M4 17h7' },
  { to: '/prompts', label: 'Prompt Studio', icon: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z' },
  { to: '/skills', label: 'Skill Studio', icon: 'M12 6V4m0 2a4 4 0 100 8m0-8a4 4 0 110 8m0 0v2m0-2c-3.314 0-6 1.343-6 3v1h12v-1c0-1.657-2.686-3-6-3z' },
  { to: '/settings', label: 'Ayarlar', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
];

const HISTORY_MAX_INDEX_KEY = 'ikas-ai-seo-agent:history-max-idx';

function isRouteActive(pathname: string, to: string) {
  if (to === '/') return pathname === '/';
  return pathname === to || pathname.startsWith(`${to}/`);
}

function BrandMark() {
  return (
    <Link
      to="/"
      className="flex min-w-0 items-center gap-2.5 rounded-2xl px-1 py-0.5 transition-opacity duration-200 hover:opacity-90"
    >
      <div
        className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[18px] text-sm font-bold text-white"
        style={{
          background: themeColors.gradient.hero,
          border: `1px solid ${themeColors.border.info}`,
          boxShadow: themeColors.shadow.hero,
        }}
      >
        AI
      </div>
      <div className="min-w-0">
        <div
          className="truncate text-[13px] font-semibold tracking-tight"
          style={{ color: 'var(--color-text-primary)' }}
        >
          ikas SEO
        </div>
        <div
          className="truncate text-[11px]"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Autonomous Engine
        </div>
      </div>
    </Link>
  );
}

function HistoryButton({
  direction,
  disabled,
  onClick,
}: {
  direction: 'back' | 'forward';
  disabled: boolean;
  onClick: () => void;
}) {
  const isBack = direction === 'back';

  return (
    <button
      type="button"
      aria-label={isBack ? 'Geri' : 'Ileri'}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-8 w-8 items-center justify-center rounded-xl transition-all duration-200 hover:-translate-y-0.5 disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-40"
      style={{
        background: themeColors.background.raised,
        border: `1px solid ${themeColors.border.strong}`,
        color: themeColors.text.secondary,
      }}
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d={isBack ? 'M15 19l-7-7 7-7' : 'M9 5l7 7-7 7'}
        />
      </svg>
    </button>
  );
}

export interface AppHeaderBreadcrumb {
  label: string;
  to?: string;
  onClick?: () => void;
}

export interface AppHeaderMeta {
  label: string;
  value: ReactNode;
  tone?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger';
}

export interface AppHeaderEyebrow {
  label: string;
  tone?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger';
  withDot?: boolean;
}

interface AppHeaderProps {
  title: string;
  description?: string;
  eyebrow?: AppHeaderEyebrow;
  breadcrumbs?: AppHeaderBreadcrumb[];
  actions?: ReactNode;
  meta?: AppHeaderMeta[];
  wrapperClassName?: string;
  panelClassName?: string;
  showPanel?: boolean;
}

function MetaCard({ item }: { item: AppHeaderMeta }) {
  const tone = item.tone ?? 'neutral';
  const accentMap: Record<NonNullable<AppHeaderMeta['tone']>, string> = {
    neutral: 'var(--color-text-secondary)',
    primary: 'var(--color-primary-light)',
    success: 'var(--color-success)',
    warning: 'var(--color-warning)',
    danger: 'var(--color-danger)',
  };

  return (
    <div
      className="min-w-[150px] max-w-[240px] rounded-xl px-3 py-2"
      style={{
        background: themeColors.background.card,
        border: `1px solid ${themeColors.border.subtle}`,
      }}
    >
      <div
        className="text-[8px] font-semibold uppercase tracking-[0.18em]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {item.label}
      </div>
      <div
        className="mt-0.5 truncate text-[11px] font-semibold sm:text-[12px]"
        style={{ color: accentMap[tone] }}
      >
        {item.value}
      </div>
    </div>
  );
}

export default function AppHeader({
  title,
  description,
  eyebrow,
  breadcrumbs = [],
  actions,
  meta = [],
  wrapperClassName = 'px-5',
  panelClassName,
  showPanel = true,
}: AppHeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const navigationType = useNavigationType();
  const [historyIndex, setHistoryIndex] = useState(0);
  const [historyMaxIndex, setHistoryMaxIndex] = useState(0);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const currentIndex =
      typeof window.history.state?.idx === 'number' ? window.history.state.idx : 0;
    const storedMaxIndex = Number(window.sessionStorage.getItem(HISTORY_MAX_INDEX_KEY) ?? '0');
    const nextMaxIndex =
      navigationType === 'PUSH'
        ? currentIndex
        : Math.max(storedMaxIndex, currentIndex);

    window.sessionStorage.setItem(HISTORY_MAX_INDEX_KEY, String(nextMaxIndex));
    setHistoryIndex(currentIndex);
    setHistoryMaxIndex(nextMaxIndex);
  }, [location.key, navigationType]);

  const canGoBack = historyIndex > 0;
  const canGoForward = historyIndex < historyMaxIndex;

  return (
    <header
      className="flex-shrink-0 border-b"
      style={{
        background: themeColors.gradient.surface,
        borderColor: themeColors.border.divider,
      }}
    >
      <div className={wrapperClassName}>
        <div className="flex flex-col gap-2 py-2.5">
          {/* ── Nav row — always identical across all pages ── */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex flex-shrink-0 items-center gap-2.5">
              <BrandMark />

              <div
                className="hidden h-5 w-px md:block"
                style={{ background: themeColors.border.subtle }}
              />

              <div className="flex items-center gap-2">
                <HistoryButton
                  direction="back"
                  disabled={!canGoBack}
                  onClick={() => navigate(-1)}
                />
                <HistoryButton
                  direction="forward"
                  disabled={!canGoForward}
                  onClick={() => navigate(1)}
                />
              </div>
            </div>

            <div className="flex flex-shrink-0 items-center gap-2">
              {NAV_ITEMS.map((item) => (
                <Link key={item.to} to={item.to}>
                  <EnterpriseNavButton active={isRouteActive(location.pathname, item.to)}>
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
                    </svg>
                    {item.label}
                  </EnterpriseNavButton>
                </Link>
              ))}

              <span
                className="rounded-full px-2.5 py-1 text-[9px] tabular-nums"
                style={{
                  background: themeColors.background.raised,
                  border: `1px solid ${themeColors.border.subtle}`,
                  color: themeColors.text.muted,
                }}
              >
                build{' '}
                {new Date(__BUILD_TIME__).toLocaleString('tr-TR', {
                  day: '2-digit',
                  month: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>

              <ThemeToggle />
            </div>
          </div>

          {/* ── Breadcrumbs row — shown independently of panel ── */}
          {breadcrumbs.length > 0 && (
            <nav className="flex flex-wrap items-center gap-1 px-1 text-[11px]">
              {breadcrumbs.map((item, index) => {
                const isCurrent = index === breadcrumbs.length - 1;
                return (
                  <div key={`${item.label}-${index}`} className="flex items-center gap-1.5">
                    {item.to ? (
                      <Link
                        to={item.to}
                        className="rounded-lg px-2 py-0.5 transition-colors hover:bg-white/[0.04]"
                        style={{ color: isCurrent ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}
                      >
                        {item.label}
                      </Link>
                    ) : item.onClick && !isCurrent ? (
                      <button
                        type="button"
                        onClick={item.onClick}
                        className="rounded-lg px-2 py-0.5 transition-colors hover:bg-white/[0.04]"
                        style={{ color: 'var(--color-text-secondary)' }}
                      >
                        {item.label}
                      </button>
                    ) : (
                      <span
                        className={classNames('rounded-lg px-2 py-0.5', isCurrent && 'font-medium')}
                        style={{ color: isCurrent ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}
                      >
                        {item.label}
                      </span>
                    )}
                    {!isCurrent && <span style={{ color: 'var(--color-text-muted)' }}>/</span>}
                  </div>
                );
              })}
            </nav>
          )}

          {showPanel ? (
            <div
              className={classNames(
                'enterprise-surface rounded-3xl px-4 py-3 sm:px-4.5',
                panelClassName,
              )}
            >
              <div className="flex flex-col gap-2.5 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    {eyebrow && (
                      <EnterprisePill tone={eyebrow.tone ?? 'primary'} className="gap-1 px-2 py-0.5 text-[8px]">
                        <span>{eyebrow.label}</span>
                        {eyebrow.withDot && (
                          <span className="h-1.5 w-1.5 rounded-full bg-current opacity-90" />
                        )}
                      </EnterprisePill>
                    )}

                    <h1
                      className="min-w-0 text-[1.75rem] font-semibold leading-tight tracking-tight sm:text-[1.95rem]"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {title}
                    </h1>
                  </div>

                  {description && (
                    <p
                      className="mt-1 max-w-3xl truncate text-[11px] leading-5 sm:text-[12px]"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      {description}
                    </p>
                  )}
                </div>

                {(meta.length > 0 || actions) && (
                  <div className="flex w-full flex-wrap items-center gap-2 lg:max-w-[62%] lg:justify-end">
                    {meta.length > 0 && (
                      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                        {meta.map((item) => (
                          <MetaCard key={item.label} item={item} />
                        ))}
                      </div>
                    )}

                    {actions && (
                      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                        {actions}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

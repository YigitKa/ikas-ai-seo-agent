/**
 * Centralised theme tokens.
 *
 * Every UI surface MUST read its colour from this file. No raw hex / rgb /
 * rgba / hsl values should live in component code or inline `style`
 * attributes. All values point at CSS variables declared in `src/index.css`,
 * which swap between light and dark themes via `[data-theme="light"]` on the
 * document element.
 *
 * If you need a new colour, add a CSS variable to `index.css` (under both
 * `:root` and `[data-theme="light"]`) and then expose it here.
 */

export const themeColors = {
  // ── Text ───────────────────────────────────────────────────────────────
  text: {
    primary: 'var(--color-text-primary)',
    secondary: 'var(--color-text-secondary)',
    muted: 'var(--color-text-muted)',
    inverse: 'var(--color-text-inverse)',
    brand: 'var(--color-text-brand)',
    brandSoft: 'var(--color-text-brand-soft)',
    info: 'var(--color-text-info)',
    success: 'var(--color-text-success)',
    successSoft: 'var(--color-text-success-soft)',
    warning: 'var(--color-text-warning)',
    warningSoft: 'var(--color-text-warning-soft)',
    danger: 'var(--color-text-danger)',
    dangerSoft: 'var(--color-text-danger-soft)',
  },

  // ── Background / surface ───────────────────────────────────────────────
  background: {
    base: 'var(--color-bg-base)',
    surface: 'var(--color-bg-surface)',
    elevated: 'var(--color-bg-elevated)',
    hover: 'var(--color-bg-hover)',
    glass: 'var(--glass-bg)',
    overlay: 'var(--color-overlay)',
    overlayDark: 'var(--color-overlay-dark)',
    toast: 'var(--color-toast-bg)',

    // Translucent chip / pill surfaces
    subtle: 'var(--surface-subtle)',
    raised: 'var(--surface-raised)',
    panel: 'var(--surface-panel)',
    card: 'var(--surface-card)',
    inputField: 'var(--surface-input)',
    codeBlock: 'var(--surface-code)',
  },

  // ── Borders / dividers ─────────────────────────────────────────────────
  border: {
    base: 'var(--color-border)',
    light: 'var(--color-border-light)',
    subtle: 'var(--color-border-subtle)',
    strong: 'var(--color-border-strong)',
    divider: 'var(--color-divider)',
    success: 'var(--color-border-success)',
    warning: 'var(--color-border-warning)',
    danger: 'var(--color-border-danger)',
    primary: 'var(--color-border-primary)',
    info: 'var(--color-border-info)',
  },

  // ── Icons ──────────────────────────────────────────────────────────────
  icon: {
    primary: 'var(--color-icon-primary)',
    success: 'var(--color-icon-success)',
    warning: 'var(--color-icon-warning)',
    danger: 'var(--color-icon-danger)',
    info: 'var(--color-icon-info)',
    muted: 'var(--color-icon-muted)',
  },

  // ── Brand / status (base palette) ──────────────────────────────────────
  brand: {
    primary: 'var(--color-primary)',
    primaryLight: 'var(--color-primary-light)',
    primaryDark: 'var(--color-primary-dark)',
    accent: 'var(--color-accent)',
    accentLight: 'var(--color-accent-light)',
  },
  status: {
    success: 'var(--color-success)',
    warning: 'var(--color-warning)',
    danger: 'var(--color-danger)',
    orange: 'var(--color-orange)',
    info: 'var(--color-info)',
  },

  // ── Score rings ────────────────────────────────────────────────────────
  score: {
    excellent: 'var(--score-excellent)',
    good: 'var(--score-good)',
    fair: 'var(--score-fair)',
    poor: 'var(--score-poor)',
  },

  // ── Tinted surface backgrounds (status + info bubbles) ─────────────────
  tint: {
    successSoft: 'var(--tint-success-soft)',
    successBg: 'var(--tint-success-bg)',
    warningSoft: 'var(--tint-warning-soft)',
    warningBg: 'var(--tint-warning-bg)',
    dangerSoft: 'var(--tint-danger-soft)',
    dangerBg: 'var(--tint-danger-bg)',
    primarySoft: 'var(--tint-primary-soft)',
    primaryBg: 'var(--tint-primary-bg)',
    infoSoft: 'var(--tint-info-soft)',
    infoBg: 'var(--tint-info-bg)',
    accentSoft: 'var(--tint-accent-soft)',
    accentBg: 'var(--tint-accent-bg)',
  },

  // ── Gradients ──────────────────────────────────────────────────────────
  gradient: {
    primary: 'var(--gradient-primary)',
    danger: 'var(--gradient-danger)',
    success: 'var(--gradient-success)',
    warning: 'var(--gradient-warning)',
    panel: 'var(--gradient-panel)',
    surface: 'var(--gradient-surface)',
    activeChip: 'var(--gradient-active-chip)',
    hero: 'var(--gradient-hero)',
    accent: 'var(--gradient-accent)',
  },

  // ── Shadows ────────────────────────────────────────────────────────────
  shadow: {
    primarySm: 'var(--shadow-primary-sm)',
    dangerSm: 'var(--shadow-danger-sm)',
    successSm: 'var(--shadow-success-sm)',
    modal: 'var(--shadow-modal)',
    hero: 'var(--shadow-hero)',
    card: 'var(--shadow-card)',
  },

  // ── White/black alphas (translucent highlights) ────────────────────────
  alpha: {
    white3: 'var(--alpha-white-3)',
    white4: 'var(--alpha-white-4)',
    white6: 'var(--alpha-white-6)',
    white8: 'var(--alpha-white-8)',
    white12: 'var(--alpha-white-12)',
    white15: 'var(--alpha-white-15)',
    black20: 'var(--alpha-black-20)',
    black40: 'var(--alpha-black-40)',
    black60: 'var(--alpha-black-60)',
  },
} as const;

export type ThemeColors = typeof themeColors;

// Convenience aliases
export const text = themeColors.text;
export const bg = themeColors.background;
export const border = themeColors.border;
export const icon = themeColors.icon;
export const brand = themeColors.brand;
export const status = themeColors.status;
export const tint = themeColors.tint;
export const gradient = themeColors.gradient;
export const shadow = themeColors.shadow;
export const alpha = themeColors.alpha;
export const score = themeColors.score;

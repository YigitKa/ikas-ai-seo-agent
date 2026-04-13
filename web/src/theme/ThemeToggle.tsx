import { useTheme } from './ThemeContext';
import { themeColors } from './colors';

interface ThemeToggleProps {
  className?: string;
}

/**
 * Light/Dark theme toggle button. Renders as a compact pill that displays
 * the icon for the *opposite* theme (i.e. the one you'd switch to).
 */
export default function ThemeToggle({ className }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      aria-label={isDark ? 'Aydinlik temaya gec' : 'Karanlik temaya gec'}
      title={isDark ? 'Aydinlik tema' : 'Karanlik tema'}
      onClick={toggleTheme}
      className={[
        'inline-flex h-8 w-8 items-center justify-center rounded-xl transition-all duration-200 hover:-translate-y-0.5',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        background: themeColors.background.raised,
        border: `1px solid ${themeColors.border.subtle}`,
        color: themeColors.text.secondary,
      }}
    >
      {isDark ? (
        /* Show sun icon (click to go light) */
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 3v1.5M12 19.5V21M4.22 4.22l1.06 1.06M18.72 18.72l1.06 1.06M3 12h1.5M19.5 12H21M4.22 19.78l1.06-1.06M18.72 5.28l1.06-1.06M12 7.5a4.5 4.5 0 100 9 4.5 4.5 0 000-9z"
          />
        </svg>
      ) : (
        /* Show moon icon (click to go dark) */
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"
          />
        </svg>
      )}
    </button>
  );
}

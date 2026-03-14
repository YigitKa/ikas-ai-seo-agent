import { useEffect, useRef, useState } from 'react';
import { getScoreColor } from '../score/scoreUtils';

// ── useCountUp hook ─────────────────────────────────────────────────────────

export function useCountUp(target: number, duration: number, delay: number): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    let startTime: number | null = null;

    const animate = (timestamp: number) => {
      if (startTime === null) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    const delayTimer = setTimeout(() => {
      rafRef.current = requestAnimationFrame(animate);
    }, delay);

    return () => {
      clearTimeout(delayTimer);
      cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration, delay]);

  return value;
}

// ── CircularScore ───────────────────────────────────────────────────────────

interface CircularScoreProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  animated?: boolean;
  delay?: number;
  /** Label shown below the number (default: "/100") */
  subtitle?: string;
}

export default function CircularScore({
  score,
  size = 76,
  strokeWidth = 5,
  animated = false,
  delay = 0,
  subtitle = '/100',
}: CircularScoreProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const color = getScoreColor(score);

  const displayValue = animated ? useCountUp(score, 1200, delay) : score;

  const [mounted, setMounted] = useState(!animated);
  useEffect(() => {
    if (!animated) return;
    const timer = setTimeout(() => setMounted(true), delay);
    return () => clearTimeout(timer);
  }, [animated, delay]);

  const offset = mounted
    ? circumference - (score / 100) * circumference
    : circumference;

  const textSize = size >= 100 ? 'text-2xl' : 'text-lg';
  const subSize = size >= 100 ? 'text-[10px]' : 'text-[9px]';

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        style={animated ? { transform: 'rotate(-90deg)' } : undefined}
        className={animated ? undefined : 'score-ring'}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
          className={animated ? undefined : 'score-ring-track'}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={animated ? undefined : 'score-ring-fill'}
          style={
            animated
              ? { transition: `stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1) ${delay}ms` }
              : undefined
          }
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className={`${textSize} font-bold`} style={{ color }}>{displayValue}</span>
        <span className={`${subSize} font-medium`} style={{ color: 'var(--color-text-muted)' }}>{subtitle}</span>
      </div>
    </div>
  );
}

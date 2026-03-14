import { useEffect, useState } from 'react';
import { getScoreGradient } from '../score/scoreUtils';

interface ProgressBarProps {
  pct: number;
  animated?: boolean;
  delay?: number;
  height?: string;
}

export default function ProgressBar({
  pct,
  animated = false,
  delay = 0,
  height = 'h-1',
}: ProgressBarProps) {
  const [mounted, setMounted] = useState(!animated);

  useEffect(() => {
    if (!animated) return;
    const timer = setTimeout(() => setMounted(true), delay);
    return () => clearTimeout(timer);
  }, [animated, delay]);

  return (
    <div
      className={`${height} w-full overflow-hidden rounded-full`}
      style={{ background: 'rgba(255,255,255,0.06)' }}
    >
      <div
        className="h-full rounded-full"
        style={{
          width: mounted ? `${pct}%` : '0%',
          background: getScoreGradient(pct),
          transition: animated
            ? `width 800ms cubic-bezier(0.4, 0, 0.2, 1) ${delay}ms`
            : 'all 700ms',
        }}
      />
    </div>
  );
}

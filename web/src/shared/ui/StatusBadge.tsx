import { getFieldStatusText, getStatusBadgeStyle } from '../score/scoreUtils';

interface StatusBadgeProps {
  pct: number;
  className?: string;
}

export default function StatusBadge({ pct, className = '' }: StatusBadgeProps) {
  const style = getStatusBadgeStyle(pct);
  const text = getFieldStatusText(pct);

  return (
    <span
      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${className}`}
      style={style}
    >
      {text}
    </span>
  );
}

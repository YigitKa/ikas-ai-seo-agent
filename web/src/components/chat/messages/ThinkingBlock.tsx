import { useState, type CSSProperties } from 'react';
import { formatThoughtDuration } from '../chatUtils';
import MarkdownMessage from './MarkdownMessage';

export function ThinkingStreamText({ text }: { text: string }) {
  const parts = text.split(/(\s+)/).filter((part) => part.length > 0);

  return (
    <div className="thinking-stream text-[12px] leading-relaxed">
      {parts.map((part, index) => {
        if (/^\s+$/.test(part)) {
          return <span key={`space-${index}`}>{part}</span>;
        }

        const animatedWordCount = parts
          .slice(0, index + 1)
          .filter((chunk) => !/^\s+$/.test(chunk))
          .length;
        const delayStep = Math.min(animatedWordCount * 0.012, 0.42);
        const style = { '--word-delay': `${delayStep}s` } as CSSProperties;

        return (
          <span key={`word-${index}`} className="thinking-word" style={style}>
            {part}
          </span>
        );
      })}
    </div>
  );
}

export default function ThinkingBlock({
  text,
  assistantLabel,
  durationSeconds,
}: {
  text: string;
  assistantLabel: string;
  durationSeconds?: number;
}) {
  const isLive = typeof durationSeconds !== 'number' || durationSeconds <= 0;
  const [expanded, setExpanded] = useState(true);
  const isExpanded = isLive ? true : expanded;

  const title =
    typeof durationSeconds === 'number' && durationSeconds > 0
      ? `Thought for ${formatThoughtDuration(durationSeconds)}`
      : `${assistantLabel} dusunce`;

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: 'linear-gradient(145deg, rgba(34, 211, 238, 0.08), rgba(15, 23, 42, 0.88))',
        border: '1px solid rgba(34, 211, 238, 0.22)',
      }}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left"
        style={{ color: '#67e8f9' }}
      >
        <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <span className="font-medium">{title}</span>
        <span className="ml-auto text-[10px]" style={{ color: 'rgba(103, 232, 249, 0.66)' }}>
          {isExpanded ? 'Gizle' : 'Goster'}
        </span>
      </button>
      {isExpanded && (
        <div className="mt-2 text-[12px] leading-relaxed" style={{ color: 'rgba(224, 242, 254, 0.88)' }}>
          {isLive ? <ThinkingStreamText text={text} /> : <MarkdownMessage content={text} />}
        </div>
      )}
    </div>
  );
}

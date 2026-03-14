import { isValidElement } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function flattenNodeText(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map(flattenNodeText).join('');
  }

  if (isValidElement<{ children?: unknown }>(value)) {
    return flattenNodeText(value.props.children);
  }

  return '';
}

export function isNarrativeCodeBlock(raw: string): boolean {
  const value = raw.trim();
  if (!value) {
    return false;
  }

  const codeIndicators = /[{};=<>]|\[|\]|\b(function|const|let|return|class|import)\b/i;
  if (codeIndicators.test(value)) {
    return false;
  }

  return /(oner|öner|seo|meta|aciklama|açıklama|title|description|✅|➡|→|\*\*)/i.test(value);
}

export default function MarkdownMessage({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => <h1 className="mb-3 text-lg font-semibold text-white">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-3 text-base font-semibold text-white">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-2 text-sm font-semibold text-white">{children}</h3>,
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote
            className="mb-3 border-l-2 pl-3 italic"
            style={{ borderColor: 'rgba(34, 211, 238, 0.35)', color: 'var(--color-text-secondary)' }}
          >
            {children}
          </blockquote>
        ),
        pre: ({ children }) => {
          const rawBlock = flattenNodeText(children);
          if (isNarrativeCodeBlock(rawBlock)) {
            return (
              <div
                className="mb-3 rounded-lg p-3 text-[12px] leading-relaxed"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: 'var(--color-text-primary)',
                }}
              >
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
                    ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
                    li: ({ children }) => <li>{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                    code: ({ children }) => <code>{children}</code>,
                  }}
                >
                  {rawBlock}
                </ReactMarkdown>
              </div>
            );
          }

          return (
            <pre
              className="mb-3 overflow-x-auto rounded-lg p-3 text-[12px]"
              style={{ background: 'rgba(0,0,0,0.18)' }}
            >
              {children}
            </pre>
          );
        },
        code: ({ className, children }) => {
          const value = String(children);
          const isInline = !className && !value.includes('\n');

          if (!isInline) {
            return <code className={className}>{children}</code>;
          }

          return (
            <code
              className="rounded px-1.5 py-0.5 text-[12px]"
              style={{ background: 'rgba(255,255,255,0.06)', color: '#c7d2fe' }}
            >
              {children}
            </code>
          );
        },
        table: ({ children }) => (
          <div className="mb-3 overflow-x-auto last:mb-0">
            <table
              className="min-w-full border-collapse text-left text-[12px]"
              style={{ border: '1px solid var(--color-border)' }}
            >
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => (
          <thead style={{ background: 'rgba(255,255,255,0.04)' }}>{children}</thead>
        ),
        th: ({ children }) => (
          <th className="px-3 py-2 font-semibold" style={{ borderBottom: '1px solid var(--color-border)' }}>
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 align-top" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            {children}
          </td>
        ),
        strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
        hr: () => <hr className="my-3" style={{ borderColor: 'var(--color-border)' }} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

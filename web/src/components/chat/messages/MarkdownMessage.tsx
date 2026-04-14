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
        h1: ({ children }) => <h1 className="mb-3 text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>{children}</h1>,
        h2: ({ children }) => <h2 className="mb-3 text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>{children}</h2>,
        h3: ({ children }) => <h3 className="mb-2 text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{children}</h3>,
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote
            className="mb-3 border-l-2 pl-3 italic"
            style={{ borderColor: 'var(--color-border-info)', color: 'var(--color-text-secondary)' }}
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
                  background: 'var(--chat-muted-card-bg)',
                  border: '1px solid var(--chat-section-border)',
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
                    strong: ({ children }) => <strong className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>{children}</strong>,
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
              style={{
                background: 'var(--surface-code)',
                border: '1px solid var(--chat-section-border)',
              }}
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
              style={{ background: 'var(--tint-primary-bg)', color: 'var(--color-text-brand-soft)' }}
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
          <thead style={{ background: 'var(--chat-muted-card-bg)' }}>{children}</thead>
        ),
        th: ({ children }) => (
          <th className="px-3 py-2 font-semibold" style={{ borderBottom: '1px solid var(--color-border)' }}>
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 align-top" style={{ borderTop: '1px solid var(--chat-section-border)' }}>
            {children}
          </td>
        ),
        strong: ({ children }) => <strong className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>{children}</strong>,
        hr: () => <hr className="my-3" style={{ borderColor: 'var(--color-border)' }} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

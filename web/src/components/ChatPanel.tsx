import { useEffect, useRef, useState } from 'react';
import { useChat, type ChatMessage } from '../hooks/useChat';
import type { ToolResult } from '../types';

interface Props {
  productId?: string;
}

function ToolResultCard({ result }: { result: ToolResult }) {
  const [expanded, setExpanded] = useState(false);
  let parsed: string;
  try {
    parsed = JSON.stringify(JSON.parse(result.result), null, 2);
  } catch {
    parsed = result.result;
  }

  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: 'rgba(245, 158, 11, 0.06)',
        border: '1px solid rgba(245, 158, 11, 0.15)',
      }}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left"
        style={{ color: '#fbbf24' }}
      >
        <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <span className="font-mono font-semibold">{result.tool}</span>
        <span style={{ color: 'rgba(245, 158, 11, 0.5)' }}>
          ({Object.keys(result.arguments).length} arg)
        </span>
        <span className="ml-auto text-[10px]" style={{ color: 'rgba(245, 158, 11, 0.6)' }}>
          {expanded ? 'Gizle' : 'Goster'}
        </span>
      </button>
      {expanded && (
        <pre
          className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md p-2 text-[11px]"
          style={{
            background: 'rgba(0,0,0,0.2)',
            color: 'rgba(245, 158, 11, 0.7)',
          }}
        >
          {parsed}
        </pre>
      )}
    </div>
  );
}

function ThinkingBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        background: 'rgba(139, 92, 246, 0.06)',
        border: '1px solid rgba(139, 92, 246, 0.15)',
      }}
    >
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left"
        style={{ color: '#a78bfa' }}
      >
        <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
        <span className="font-medium">Dusunce</span>
        <span className="ml-auto text-[10px]" style={{ color: 'rgba(139, 92, 246, 0.6)' }}>
          {expanded ? 'Gizle' : 'Goster'}
        </span>
      </button>
      {expanded && (
        <p className="mt-2 whitespace-pre-wrap text-[12px] leading-relaxed" style={{ color: 'rgba(139, 92, 246, 0.7)' }}>
          {text}
        </p>
      )}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const isAssistant = msg.role === 'assistant';

  return (
    <div className="space-y-2">
      {/* Tool results */}
      {isAssistant && msg.toolResults && msg.toolResults.length > 0 && (
        <div className="mr-6 space-y-1.5">
          {msg.toolResults.map((tr, i) => (
            <ToolResultCard key={i} result={tr} />
          ))}
        </div>
      )}

      {/* Thinking */}
      {isAssistant && msg.thinking ? <ThinkingBlock text={msg.thinking} /> : null}

      {/* Main message */}
      <div
        className={`rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
          isUser ? 'ml-6' : isSystem ? '' : 'mr-6'
        }`}
        style={{
          background: isUser
            ? 'rgba(99, 102, 241, 0.15)'
            : isSystem
              ? 'rgba(255, 255, 255, 0.03)'
              : 'var(--color-bg-elevated)',
          border: isSystem ? 'none' : `1px solid ${isUser ? 'rgba(99, 102, 241, 0.2)' : 'var(--color-border)'}`,
          color: isUser
            ? '#c7d2fe'
            : isSystem
              ? 'var(--color-text-muted)'
              : 'var(--color-text-primary)',
          fontStyle: isSystem ? 'italic' : 'normal',
          fontSize: isSystem ? '12px' : '13px',
        }}
      >
        {isAssistant ? (
          <div
            dangerouslySetInnerHTML={{
              __html: msg.content
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\n/g, '<br/>'),
            }}
          />
        ) : (
          msg.content
        )}
      </div>

      {/* Token usage */}
      {isAssistant && msg.meta && (msg.meta.input_tokens || msg.meta.output_tokens) ? (
        <div className="mr-6 text-right text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
          {String(msg.meta.input_tokens ?? 0)}+{String(msg.meta.output_tokens ?? 0)} tokens
          {msg.meta.model ? <span> &middot; {String(msg.meta.model)}</span> : null}
        </div>
      ) : null}
    </div>
  );
}

export default function ChatPanel({ productId }: Props) {
  const { messages, isLoading, mcpState, sendMessage, clearHistory, connect } =
    useChat(productId);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    connect();
  }, [connect]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;
    sendMessage(text);
    setInput('');
  };

  return (
    <div
      className="flex h-full flex-col rounded-xl overflow-hidden"
      style={{
        background: 'var(--color-bg-surface)',
        border: '1px solid var(--color-border)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center gap-2">
          <div
            className="flex h-6 w-6 items-center justify-center rounded-md"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            <svg className="h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <span className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            AI Chat
          </span>
          {mcpState.initialized && (
            <span
              className="rounded-full px-1.5 py-0.5 text-[9px] font-semibold"
              style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#34d399' }}
            >
              MCP
            </span>
          )}
          {mcpState.hasToken && !mcpState.initialized && (
            <span
              className="rounded-full px-1.5 py-0.5 text-[9px] font-semibold animate-pulse-dot"
              style={{ background: 'rgba(245, 158, 11, 0.12)', color: '#fbbf24' }}
            >
              MCP bekliyor
            </span>
          )}
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearHistory}
            className="text-[11px] font-medium transition-all"
            style={{ color: 'var(--color-text-muted)' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-secondary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-muted)')}
          >
            Temizle
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center py-8">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-xl"
              style={{ background: 'var(--glass-bg)', border: '1px solid var(--color-border)' }}
            >
              <svg className="h-5 w-5" style={{ color: 'var(--color-text-muted)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              SEO hakkinda sorularinizi sorun...
            </p>
            {mcpState.initialized && (
              <p className="text-[11px]" style={{ color: 'rgba(16, 185, 129, 0.6)' }}>
                MCP bagli — ikas magaza verilerine erisim aktif
              </p>
            )}
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {isLoading && (
          <div
            className="mr-6 flex items-center gap-2 rounded-xl px-4 py-3"
            style={{
              background: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border)',
            }}
          >
            <div className="flex gap-1">
              <span className="typing-dot h-1.5 w-1.5 rounded-full" style={{ background: 'var(--color-primary-light)' }} />
              <span className="typing-dot h-1.5 w-1.5 rounded-full" style={{ background: 'var(--color-primary-light)' }} />
              <span className="typing-dot h-1.5 w-1.5 rounded-full" style={{ background: 'var(--color-primary-light)' }} />
            </div>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Dusunuyor...
            </span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-3" style={{ borderTop: '1px solid var(--color-border)' }}>
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder={
              mcpState.initialized
                ? 'MCP aktif — magaza verilerini sorgulayabilirsiniz...'
                : 'Mesaj yazin...'
            }
            className="flex-1 rounded-lg px-3 py-2 text-[13px] outline-none transition-all"
            style={{
              background: 'var(--color-bg-base)',
              border: '1px solid var(--color-border-light)',
              color: 'var(--color-text-primary)',
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--color-primary)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--color-border-light)')}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg text-white transition-all hover:opacity-90 disabled:opacity-30"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

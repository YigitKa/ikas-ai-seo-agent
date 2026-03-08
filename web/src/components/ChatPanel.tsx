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
    <div className="rounded border border-amber-700/40 bg-amber-900/10 px-2.5 py-1.5 text-xs">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left text-amber-300"
      >
        <span className="font-mono font-semibold">{result.tool}</span>
        <span className="text-amber-500/70">
          ({Object.keys(result.arguments).length} arg)
        </span>
        <span className="ml-auto text-[10px] text-amber-500">
          {expanded ? 'Gizle' : 'Goster'}
        </span>
      </button>
      {expanded && (
        <pre className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap text-[11px] text-amber-200/70">
          {parsed}
        </pre>
      )}
    </div>
  );
}

function ThinkingBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded border border-purple-700/30 bg-purple-900/10 px-2.5 py-1.5 text-xs">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left text-purple-300"
      >
        <span className="font-medium">Dusunce</span>
        <span className="ml-auto text-[10px] text-purple-500">
          {expanded ? 'Gizle' : 'Goster'}
        </span>
      </button>
      {expanded && (
        <p className="mt-1.5 whitespace-pre-wrap text-purple-200/70">{text}</p>
      )}
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const isAssistant = msg.role === 'assistant';

  return (
    <div className="space-y-1.5">
      {/* Tool results (shown before the response) */}
      {isAssistant && msg.toolResults && msg.toolResults.length > 0 && (
        <div className="mr-8 space-y-1">
          {msg.toolResults.map((tr, i) => (
            <ToolResultCard key={i} result={tr} />
          ))}
        </div>
      )}

      {/* Thinking block */}
      {isAssistant && msg.thinking ? <ThinkingBlock text={msg.thinking} /> : null}

      {/* Main message */}
      <div
        className={`rounded-lg px-3 py-2 text-sm ${
          isUser
            ? 'ml-8 bg-blue-600/20 text-blue-200'
            : isSystem
              ? 'bg-gray-700/30 text-gray-400 text-xs italic'
              : 'mr-8 bg-gray-700/50 text-gray-200'
        }`}
      >
        {isAssistant ? (
          <div
            className="prose prose-sm prose-invert max-w-none"
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
        <div className="mr-8 text-right text-[10px] text-gray-600">
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
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;
    sendMessage(text);
    setInput('');
  };

  return (
    <div className="flex h-full flex-col rounded-xl border border-gray-700 bg-gray-800/50">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-300">AI Chat</h3>
          {mcpState.initialized && (
            <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-medium text-green-400">
              MCP
            </span>
          )}
          {mcpState.hasToken && !mcpState.initialized && (
            <span className="rounded-full bg-yellow-500/20 px-2 py-0.5 text-[10px] font-medium text-yellow-400">
              MCP bekliyor
            </span>
          )}
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearHistory}
            className="text-xs text-gray-500 hover:text-gray-300 transition"
          >
            Temizle
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-xs text-gray-500 space-y-1">
            <p>SEO hakkinda sorularinizi sorun...</p>
            {mcpState.initialized && (
              <p className="text-green-500/70">
                MCP bagli — ikas magaza verilerine erisim aktif
              </p>
            )}
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {isLoading && (
          <div className="mr-8 rounded-lg bg-gray-700/30 px-3 py-2 text-sm text-gray-400 animate-pulse">
            Dusunuyor...
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-700 p-3">
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
            className="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 outline-none focus:border-blue-500"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            Gonder
          </button>
        </div>
      </div>
    </div>
  );
}

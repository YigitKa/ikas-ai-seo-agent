import { useEffect, useRef, useState } from 'react';
import { useChat } from '../hooks/useChat';

interface Props {
  productId?: string;
}

export default function ChatPanel({ productId }: Props) {
  const { messages, isLoading, sendMessage, connect } = useChat(productId);
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
      <div className="border-b border-gray-700 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-300">AI Chat</h3>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-center text-xs text-gray-500">
            SEO hakkinda sorularinizi sorun...
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`rounded-lg px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'ml-8 bg-blue-600/20 text-blue-200'
                : msg.role === 'system'
                  ? 'bg-red-600/10 text-red-300'
                  : 'mr-8 bg-gray-700/50 text-gray-200'
            }`}
          >
            {msg.content}
          </div>
        ))}
        {isLoading && (
          <div className="mr-8 rounded-lg bg-gray-700/30 px-3 py-2 text-sm text-gray-400 animate-pulse">
            Dusunuyor...
          </div>
        )}
      </div>

      <div className="border-t border-gray-700 p-3">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Mesaj yazin..."
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

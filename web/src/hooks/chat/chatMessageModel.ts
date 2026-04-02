import type { ChatResponseMeta, SeoSuggestion, SuggestionSavedInfo, ToolResult } from '../../types';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  thinking?: string;
  toolResults?: ToolResult[];
  meta?: ChatResponseMeta;
  suggestionSaved?: SuggestionSavedInfo;
  pendingSuggestion?: SeoSuggestion | null;
}

export type ChatMessageDraft = Omit<ChatMessage, 'id'> & { id?: string };

let messageSequence = 0;

function createMessageId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  messageSequence += 1;
  return `chat-msg-${Date.now().toString(36)}-${messageSequence.toString(36)}`;
}

export function createChatMessage(message: ChatMessageDraft): ChatMessage {
  return {
    ...message,
    id: message.id ?? createMessageId(),
  };
}

export function normalizeChatMessages(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((message) => createChatMessage(message));
}

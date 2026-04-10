import { render, waitFor } from '@testing-library/react';
import ChatPanel from './ChatPanel';

const connectSpy = vi.fn();
const disconnectSpy = vi.fn();
const sendMessageSpy = vi.fn();
const invalidateQueriesSpy = vi.fn();

vi.mock('@tanstack/react-query', () => ({
  useQuery: vi.fn(({ queryKey }: { queryKey: string[] }) => {
    if (queryKey[0] === 'settings') {
      return {
        data: {
          ai_model_name: 'gpt-test',
          ai_provider: 'openai',
        },
        isLoading: false,
      };
    }
    if (queryKey[0] === 'skills') {
      return {
        data: { items: [] },
        isLoading: false,
      };
    }
    return {
      data: null,
      isLoading: false,
    };
  }),
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesSpy,
  }),
}));

vi.mock('../api/client', () => ({
  getLmStudioLiveStatus: vi.fn(),
  getSettings: vi.fn(),
  getSkills: vi.fn(),
}));

vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    messages: [],
    isLoading: false,
    isReconnecting: false,
    isAutoIntroActive: false,
    pendingSince: null,
    liveChunkCount: 0,
    liveTokenEstimate: 0,
    pendingSuggestion: null,
    activeSkill: null,
    mcpState: {
      hasToken: true,
      initialized: true,
      toolCount: 3,
      tools: [],
      message: '',
    },
    sendMessage: sendMessageSpy,
    retryLastMessage: vi.fn(),
    addLocalMessage: vi.fn(),
    cancelMessage: vi.fn(),
    clearHistory: vi.fn(),
    setActiveSkill: vi.fn(),
    clearActiveSkill: vi.fn(),
    connect: connectSpy,
    disconnect: disconnectSpy,
  }),
}));

vi.mock('./chat/ChatPanelUi', () => ({
  ReconnectingBanner: () => <div data-testid="reconnecting-banner" />,
}));

vi.mock('./chat/ChatHeader', () => ({
  ChatHeader: () => <div data-testid="chat-header" />,
}));

vi.mock('./chat/ChatMessages', () => ({
  ChatMessages: () => <div data-testid="chat-messages" />,
}));

vi.mock('./chat/ChatInput', () => ({
  ChatInput: () => <div data-testid="chat-input" />,
}));

vi.mock('./chat/SuggestionDiffModal', () => ({
  default: () => <div data-testid="suggestion-diff-modal" />,
}));

vi.mock('./chat/chatUtils', () => ({
  exportChatAsText: vi.fn(),
  formatCompactNumber: (value: number) => String(value),
  formatDuration: (value: number) => String(value),
  readMetaNumber: () => null,
}));

describe('ChatPanel pending starter messages', () => {
  beforeEach(() => {
    connectSpy.mockReset();
    disconnectSpy.mockReset();
    sendMessageSpy.mockReset();
    invalidateQueriesSpy.mockReset();
  });

  it('does not send anything when no pending message is provided', () => {
    render(<ChatPanel chatScope="store" />);

    expect(sendMessageSpy).not.toHaveBeenCalled();
    expect(connectSpy).toHaveBeenCalledTimes(1);
  });

  it('sends a pending message once and acknowledges that it was consumed', async () => {
    const onPendingMessageConsumed = vi.fn();

    render(
      <ChatPanel
        chatScope="store"
        pendingMessage={{ id: 'store-prompt-1', text: 'Aktif kampanyalari goster.' }}
        onPendingMessageConsumed={onPendingMessageConsumed}
      />,
    );

    await waitFor(() => expect(sendMessageSpy).toHaveBeenCalledWith('Aktif kampanyalari goster.'));
    expect(sendMessageSpy).toHaveBeenCalledTimes(1);
    expect(onPendingMessageConsumed).toHaveBeenCalledWith('store-prompt-1');
  });

  it('does not resend the same pending message id on rerender', async () => {
    const onPendingMessageConsumed = vi.fn();
    const pendingMessage = { id: 'store-prompt-2', text: 'Bugunun satis ozetini cikar.' };
    const { rerender } = render(
      <ChatPanel
        chatScope="store"
        pendingMessage={pendingMessage}
        onPendingMessageConsumed={onPendingMessageConsumed}
      />,
    );

    await waitFor(() => expect(sendMessageSpy).toHaveBeenCalledTimes(1));

    rerender(
      <ChatPanel
        chatScope="store"
        pendingMessage={pendingMessage}
        onPendingMessageConsumed={onPendingMessageConsumed}
      />,
    );

    expect(sendMessageSpy).toHaveBeenCalledTimes(1);
    expect(onPendingMessageConsumed).toHaveBeenCalledTimes(1);
  });

  it('sends a new request when the pending message id changes even if the text stays the same', async () => {
    const onPendingMessageConsumed = vi.fn();
    const { rerender } = render(
      <ChatPanel
        chatScope="store"
        pendingMessage={{ id: 'store-prompt-3', text: 'Stoku kritik seviyede olan urunleri listele.' }}
        onPendingMessageConsumed={onPendingMessageConsumed}
      />,
    );

    await waitFor(() => expect(sendMessageSpy).toHaveBeenCalledTimes(1));

    rerender(
      <ChatPanel
        chatScope="store"
        pendingMessage={{ id: 'store-prompt-4', text: 'Stoku kritik seviyede olan urunleri listele.' }}
        onPendingMessageConsumed={onPendingMessageConsumed}
      />,
    );

    await waitFor(() => expect(sendMessageSpy).toHaveBeenCalledTimes(2));
    expect(onPendingMessageConsumed).toHaveBeenNthCalledWith(1, 'store-prompt-3');
    expect(onPendingMessageConsumed).toHaveBeenNthCalledWith(2, 'store-prompt-4');
  });
});

import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import StoreChatAdvisor from './StoreChatAdvisor';

interface MockChatPanelProps {
  chatScope?: 'product' | 'store';
  starterPrompts?: { label: string; template: string }[];
  pendingMessage?: { id: string; text: string } | null;
  onPendingMessageConsumed?: (messageId: string) => void;
}

const chatPanelPropsSpy = vi.fn();
let latestChatPanelProps: MockChatPanelProps | null = null;

vi.mock('../ChatPanel', () => ({
  default: (props: MockChatPanelProps) => {
    latestChatPanelProps = props;
    chatPanelPropsSpy(props);
    return <div data-testid="mock-chat-panel">Mock Chat Panel</div>;
  },
}));

describe('StoreChatAdvisor', () => {
  beforeEach(() => {
    latestChatPanelProps = null;
    chatPanelPropsSpy.mockReset();
  });

  it('toggles category cards open and closed', async () => {
    const user = userEvent.setup();

    render(<StoreChatAdvisor isOpen onClose={vi.fn()} storeName="yesilgrov" />);

    expect(screen.queryByRole('button', { name: 'Son siparisleri goster' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Siparisler/ }));
    expect(screen.getByRole('button', { name: 'Son siparisleri goster' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Siparisler/ }));
    expect(screen.queryByRole('button', { name: 'Son siparisleri goster' })).not.toBeInTheDocument();
  });

  it('passes the selected store prompt into ChatPanel and clears it when consumed', async () => {
    const user = userEvent.setup();

    render(<StoreChatAdvisor isOpen onClose={vi.fn()} storeName="yesilgrov" />);

    await user.click(screen.getByRole('button', { name: /Siparisler/ }));
    await user.click(screen.getByRole('button', { name: 'Son siparisleri goster' }));

    await screen.findByTestId('mock-chat-panel');
    await waitFor(() => expect(latestChatPanelProps?.pendingMessage).not.toBeNull());

    const pendingMessage = latestChatPanelProps?.pendingMessage;
    expect(latestChatPanelProps?.chatScope).toBe('store');
    expect(pendingMessage?.text).toBe('Son siparisleri listele.');

    await act(async () => {
      latestChatPanelProps?.onPendingMessageConsumed?.(pendingMessage?.id ?? '');
    });

    await waitFor(() => expect(latestChatPanelProps?.pendingMessage).toBeNull());
  });

  it('opens free chat without queueing a starter prompt', async () => {
    const user = userEvent.setup();

    render(<StoreChatAdvisor isOpen onClose={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Serbest sohbete basla' }));

    await screen.findByTestId('mock-chat-panel');
    expect(latestChatPanelProps?.pendingMessage).toBeNull();
  });

  it('drops the old pending prompt when returning to categories and creates a new request for the next selection', async () => {
    const user = userEvent.setup();

    render(<StoreChatAdvisor isOpen onClose={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: /Siparisler/ }));
    await user.click(screen.getByRole('button', { name: 'Son siparisleri goster' }));

    await screen.findByTestId('mock-chat-panel');
    await waitFor(() => expect(latestChatPanelProps?.pendingMessage).not.toBeNull());
    const firstPendingMessage = latestChatPanelProps?.pendingMessage;

    await user.click(screen.getByRole('button', { name: 'Kategorilere don' }));
    expect(screen.getByRole('button', { name: 'Serbest sohbete basla' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Siparisler/ }));
    await user.click(screen.getByRole('button', { name: 'Son siparisleri goster' }));

    await screen.findByTestId('mock-chat-panel');
    await waitFor(() => expect(latestChatPanelProps?.pendingMessage).not.toBeNull());

    const secondPendingMessage = latestChatPanelProps?.pendingMessage;
    expect(secondPendingMessage?.text).toBe(firstPendingMessage?.text);
    expect(secondPendingMessage?.id).not.toBe(firstPendingMessage?.id);
  });

  it('resets expanded categories and chat mode after the close animation finishes', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { rerender } = render(<StoreChatAdvisor isOpen onClose={onClose} />);

    await user.click(screen.getByRole('button', { name: /Siparisler/ }));
    await user.click(screen.getByRole('button', { name: 'Son siparisleri goster' }));
    await screen.findByTestId('mock-chat-panel');

    await user.click(screen.getByRole('button', { name: 'Kapat' }));
    expect(onClose).toHaveBeenCalledTimes(1);

    rerender(<StoreChatAdvisor isOpen={false} onClose={onClose} />);
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 400));
    });
    rerender(<StoreChatAdvisor isOpen onClose={onClose} />);

    expect(screen.queryByTestId('mock-chat-panel')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Son siparisleri goster' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Serbest sohbete basla' })).toBeInTheDocument();
  });
});

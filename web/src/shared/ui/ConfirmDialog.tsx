import Modal from './Modal';

interface ConfirmDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'default';
}

export default function ConfirmDialog({
  open,
  onConfirm,
  onCancel,
  title,
  message,
  confirmLabel = 'Onayla',
  cancelLabel = 'Iptal',
  variant = 'default',
}: ConfirmDialogProps) {
  const confirmStyle =
    variant === 'danger'
      ? { background: 'linear-gradient(135deg, #ef4444, #dc2626)', color: 'white', boxShadow: '0 4px 12px rgba(239, 68, 68, 0.3)' }
      : { background: 'linear-gradient(135deg, #6366f1, #4f46e5)', color: 'white', boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)' };

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      maxWidth="max-w-md"
      footer={
        <>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl px-5 py-2.5 text-sm font-medium transition-all hover:opacity-80"
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: 'var(--color-text-secondary)',
            }}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-xl px-5 py-2.5 text-sm font-semibold transition-all hover:opacity-90"
            style={confirmStyle}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
        {message}
      </p>
    </Modal>
  );
}

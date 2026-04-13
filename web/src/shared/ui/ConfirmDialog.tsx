import Modal from './Modal';
import { themeColors } from '../../theme/colors';

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
      ? { background: themeColors.gradient.danger, color: themeColors.text.inverse, boxShadow: themeColors.shadow.dangerSm }
      : { background: themeColors.gradient.primary, color: themeColors.text.inverse, boxShadow: themeColors.shadow.primarySm };

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
              background: themeColors.alpha.white6,
              border: `1px solid ${themeColors.alpha.white12}`,
              color: themeColors.text.secondary,
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

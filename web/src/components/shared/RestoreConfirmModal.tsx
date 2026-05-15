import Dialog from '../ui/Dialog';
import Button from '../ui/Button';
import './RestoreConfirmModal.css';

export interface RestoreConfirmModalProps {
  entityType: 'firm' | 'partner';
  entityName: string;
  isOpen: boolean;
  isRestoring: boolean;
  error?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function RestoreConfirmModal({
  entityType,
  entityName,
  isOpen,
  isRestoring,
  error,
  onConfirm,
  onCancel,
}: RestoreConfirmModalProps) {
  function bodyText(): string {
    if (entityType === 'partner') {
      return `This will make ${entityName} visible again in their firm's partner list.`;
    }
    return `This will restore ${entityName} to the firms list. Partners that were auto-deleted when this firm was deleted remain deleted — restore them individually if needed.`;
  }

  return (
    <Dialog
      open={isOpen}
      onClose={onCancel}
      className="restore-confirm-dialog"
      title={`Restore ${entityName}?`}
      children={
        <div className="restore-confirm__body">
          {error ? (
            <div className="restore-confirm__error" role="alert">{error}</div>
          ) : (
            <p className="restore-confirm__text">{bodyText()}</p>
          )}
        </div>
      }
      footer={
        <>
          <Button variant="ghost" type="button" onClick={onCancel} disabled={isRestoring}>
            Cancel
          </Button>
          <Button
            variant="secondary"
            type="button"
            onClick={onConfirm}
            loading={isRestoring}
            disabled={isRestoring}
          >
            Restore
          </Button>
        </>
      }
    />
  );
}

export default RestoreConfirmModal;

import { useState } from 'react';
import Dialog from '../ui/Dialog';
import Button from '../ui/Button';
import './DeleteConfirmModal.css';

export interface DeleteConfirmModalProps {
  entityType: 'firm' | 'partner';
  entityName: string;
  partnerCount?: number;
  isOpen: boolean;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteConfirmModal({
  entityType,
  entityName,
  partnerCount = 0,
  isOpen,
  isDeleting,
  onConfirm,
  onCancel,
}: DeleteConfirmModalProps) {
  const [checked, setChecked] = useState(false);

  // Reset checkbox when modal closes.
  if (!isOpen && checked) setChecked(false);

  function body(): string {
    if (entityType === 'partner') {
      return `This will hide ${entityName} from all views. Their contact history is preserved. You can restore them from the firm detail page.`;
    }
    if (partnerCount > 0) {
      const s = partnerCount === 1 ? '' : 's';
      return `${entityName} has ${partnerCount} active partner${s}. Deleting this firm will also soft-delete them. Contact history is preserved. Restore each individually if needed.`;
    }
    return `${entityName} will be hidden from all views. You can restore it from the firms list.`;
  }

  return (
    <Dialog
      open={isOpen}
      onClose={onCancel}
      className="delete-confirm-dialog"
      title={`Delete ${entityName}?`}
      children={
        <div className="delete-confirm__body">
          <p className="delete-confirm__text">{body()}</p>
          <label className="delete-confirm__check">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
            />
            I understand this action can be undone
          </label>
        </div>
      }
      footer={
        <>
          <Button variant="ghost" type="button" onClick={onCancel} disabled={isDeleting}>
            Cancel
          </Button>
          <button
            type="button"
            className="delete-confirm__delete-btn"
            disabled={!checked || isDeleting}
            onClick={onConfirm}
          >
            {isDeleting && <span className="delete-confirm__spinner" aria-hidden="true" />}
            <span>Delete {entityName}</span>
          </button>
        </>
      }
    />
  );
}

export default DeleteConfirmModal;

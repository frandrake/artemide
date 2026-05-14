import clsx from 'clsx';
import { useEffect, useRef, type ReactNode } from 'react';
import './Dialog.css';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  ariaLabel?: string;
}

export function Dialog({ open, onClose, title, description, children, footer, ariaLabel }: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    const previouslyFocused = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="dialog-backdrop" role="presentation" onClick={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        tabIndex={-1}
        className={clsx('dialog')}
        onClick={(e) => e.stopPropagation()}
      >
        {title && <h2 className="dialog__title">{title}</h2>}
        {description && <p className="dialog__description">{description}</p>}
        {children && <div className="dialog__body">{children}</div>}
        {footer && <div className="dialog__footer">{footer}</div>}
      </div>
    </div>
  );
}

export default Dialog;

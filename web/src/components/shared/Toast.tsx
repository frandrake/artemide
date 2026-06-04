import { useEffect, useState } from 'react';
import './Toast.css';

export interface ToastProps {
  message: string;
  tone?: 'info' | 'error';
  onDismiss: () => void;
}

export function Toast({ message, tone = 'info', onDismiss }: ToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onDismiss, 200); // let fade finish
    }, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div
      className={`toast toast--${tone}${visible ? '' : ' toast--fade'}`}
      role={tone === 'error' ? 'alert' : 'status'}
      aria-live={tone === 'error' ? 'assertive' : 'polite'}
    >
      <span className="toast__message">{message}</span>
      <button
        type="button"
        className="toast__close"
        aria-label="Dismiss"
        onClick={() => { setVisible(false); setTimeout(onDismiss, 200); }}
      >
        ×
      </button>
    </div>
  );
}

export default Toast;

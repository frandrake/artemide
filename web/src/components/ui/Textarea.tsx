import clsx from 'clsx';
import { forwardRef, type TextareaHTMLAttributes } from 'react';
import './form.css';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, id, className, rows = 4, ...rest }, ref,
) {
  const inputId = id ?? rest.name;
  return (
    <div className={clsx('form-field', error && 'form-field--error', className)}>
      {label && <label className="form-label" htmlFor={inputId}>{label}</label>}
      <textarea ref={ref} id={inputId} rows={rows} className="form-input form-input--textarea" {...rest} />
      {error
        ? <p className="form-message form-message--error" role="alert">{error}</p>
        : hint
          ? <p className="form-message">{hint}</p>
          : null}
    </div>
  );
});

export default Textarea;

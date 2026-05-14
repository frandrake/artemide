import clsx from 'clsx';
import { forwardRef, type InputHTMLAttributes } from 'react';
import './form.css';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, id, className, ...rest }, ref,
) {
  const inputId = id ?? rest.name;
  return (
    <div className={clsx('form-field', error && 'form-field--error', className)}>
      {label && <label className="form-label" htmlFor={inputId}>{label}</label>}
      <input ref={ref} id={inputId} className="form-input" {...rest} />
      {error
        ? <p className="form-message form-message--error" role="alert">{error}</p>
        : hint
          ? <p className="form-message">{hint}</p>
          : null}
    </div>
  );
});

export default Input;

import clsx from 'clsx';
import { forwardRef, type SelectHTMLAttributes, type ReactNode } from 'react';
import './form.css';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, id, className, children, ...rest }, ref,
) {
  const inputId = id ?? rest.name;
  return (
    <div className={clsx('form-field', error && 'form-field--error', className)}>
      {label && <label className="form-label" htmlFor={inputId}>{label}</label>}
      <select ref={ref} id={inputId} className="form-input form-input--select" {...rest}>
        {children}
      </select>
      {error
        ? <p className="form-message form-message--error" role="alert">{error}</p>
        : hint
          ? <p className="form-message">{hint}</p>
          : null}
    </div>
  );
});

export default Select;

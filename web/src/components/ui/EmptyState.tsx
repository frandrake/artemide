import type { ReactNode } from 'react';
import './EmptyState.css';

export interface EmptyStateProps {
  title: ReactNode;
  description?: ReactNode;
  cta?: ReactNode;
}

export function EmptyState({ title, description, cta }: EmptyStateProps) {
  return (
    <div className="empty">
      <h3 className="empty__title">{title}</h3>
      {description && <p className="empty__description">{description}</p>}
      {cta && <div className="empty__cta">{cta}</div>}
    </div>
  );
}

export default EmptyState;

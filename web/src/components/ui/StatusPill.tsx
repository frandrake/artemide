import clsx from 'clsx';
import './StatusPill.css';

export type RelationshipState =
  | 'cold' | 'warming' | 'warm' | 'dormant' | 'overdue' | 'due_soon';

export interface StatusPillProps {
  state: RelationshipState;
  label?: string;
  className?: string;
}

const DEFAULT_LABELS: Record<RelationshipState, string> = {
  cold: 'cold',
  warming: 'warming',
  warm: 'warm',
  dormant: 'dormant',
  overdue: 'overdue',
  due_soon: 'due soon',
};

export function StatusPill({ state, label, className }: StatusPillProps) {
  return (
    <span className={clsx('status-pill', `status-pill--${state}`, className)}>
      {label ?? DEFAULT_LABELS[state]}
    </span>
  );
}

export default StatusPill;

import clsx from 'clsx';
import type { ReactNode } from 'react';
import './Badge.css';

export type BadgeTone = 'neutral' | 'info' | 'accent';

export interface BadgeProps {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
}

export function Badge({ tone = 'neutral', className, children }: BadgeProps) {
  return <span className={clsx('badge', `badge--${tone}`, className)}>{children}</span>;
}

export default Badge;

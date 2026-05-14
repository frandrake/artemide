import clsx from 'clsx';
import type { HTMLAttributes, ReactNode } from 'react';
import './Card.css';

export interface CardProps extends HTMLAttributes<HTMLElement> {
  padded?: boolean;
  bordered?: boolean;
  as?: 'div' | 'section' | 'article';
  children: ReactNode;
}

export function Card({
  padded = true,
  bordered = true,
  as: Tag = 'section',
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <Tag
      className={clsx('card', padded && 'card--padded', bordered && 'card--bordered', className)}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export default Card;

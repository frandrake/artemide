import clsx from 'clsx';
import type { CSSProperties } from 'react';
import './Skeleton.css';

export interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  className?: string;
}

export function Skeleton({ width = '100%', height = 16, radius = 2, className }: SkeletonProps) {
  const style: CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
    borderRadius: typeof radius === 'number' ? `${radius}px` : radius,
  };
  return <span className={clsx('skeleton', className)} style={style} aria-hidden="true" />;
}

export default Skeleton;

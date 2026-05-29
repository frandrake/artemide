import type { Engagement, Rag } from '../../lib/types';

export function fitTone(e: Engagement): 'high' | 'mid' | 'fail' {
  const bd = e.fit_breakdown;
  const hardFail = bd && typeof bd === 'object' && (bd as Record<string, unknown>).hard_fail === true;
  if (hardFail) return 'fail';
  if (e.fit_score != null && e.fit_score >= 70) return 'high';
  return 'mid';
}

export function gbp(n: number | null | undefined): string {
  if (n == null) return '—';
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 }).format(n);
}

export function ragClass(rag: Rag): string {
  return `rag--${rag}`;
}

export function ulidFromPath(prefix: string): string | null {
  if (typeof window === 'undefined') return null;
  const m = window.location.pathname.match(new RegExp(`^/${prefix}/([0-9A-HJKMNP-TV-Z]{26})/?$`, 'i'));
  return m ? m[1] : null;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, ' ');
}

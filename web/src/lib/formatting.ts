import { format, formatDistanceToNowStrict, parseISO } from 'date-fns';
import type { ContactChannel } from './types';

export function formatAbsoluteDate(value: string | Date): string {
  const d = typeof value === 'string' ? parseISO(value) : value;
  return format(d, 'd LLL yyyy');
}

export function formatRelativeDate(value: string | Date): string {
  const d = typeof value === 'string' ? parseISO(value) : value;
  return `${formatDistanceToNowStrict(d, { addSuffix: true })}`;
}

export function formatInt(value: number): string {
  return new Intl.NumberFormat('en-GB').format(value);
}

// Lucide icon names per channel. The consuming component imports the
// matching icon module from lucide-react when rendering.
const CHANNEL_ICONS: Record<ContactChannel, string> = {
  email: 'mail',
  call: 'phone',
  coffee: 'coffee',
  event: 'calendar',
  inmail: 'linkedin',
  message: 'message-square',
  other: 'circle',
};

export const channelIconName = (channel: ContactChannel): string =>
  CHANNEL_ICONS[channel] ?? 'circle';

export function pluralise(n: number, singular: string, plural?: string): string {
  return n === 1 ? singular : (plural ?? `${singular}s`);
}

// Human-readable byte size, e.g. 1536 -> "1.5 KB".
export function bytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return '—';
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB'];
  let value = n / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || Number.isInteger(value) ? 0 : 1)} ${units[unit]}`;
}

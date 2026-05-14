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

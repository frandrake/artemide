import { useState } from 'react';
import type { ContactLog } from '../../lib/types';
import { formatAbsoluteDate, channelIconName } from '../../lib/formatting';
import './Timeline.css';

export interface TimelineProps {
  contacts: ContactLog[];
  partnerLookup?: Record<string, string>;
}

export default function Timeline({ contacts, partnerLookup }: TimelineProps) {
  const [openUlid, setOpenUlid] = useState<string | null>(null);
  if (contacts.length === 0) {
    return <p className="timeline__empty">No contact yet.</p>;
  }
  return (
    <ol className="timeline">
      {contacts.map((c) => {
        const isOpen = openUlid === c.ulid;
        const hasDetails = c.value_given || c.value_received || c.follow_up;
        return (
          <li key={c.ulid} className="timeline__row">
            <div className="timeline__channel" aria-label={c.channel}>
              <ChannelGlyph channel={c.channel} />
            </div>
            <div className="timeline__main">
              <div className="timeline__head">
                <span className="timeline__date">{formatAbsoluteDate(c.contact_date)}</span>
                {partnerLookup && (
                  <span className="timeline__partner">
                    {partnerLookup[String((c as ContactLog & { partner_id?: number }).partner_id ?? '')] ?? ''}
                  </span>
                )}
                <span className="timeline__channel-label">{c.channel}</span>
              </div>
              {c.summary && <p className="timeline__summary">{c.summary}</p>}
              {hasDetails && (
                <button
                  type="button"
                  className="timeline__toggle"
                  aria-expanded={isOpen}
                  onClick={() => setOpenUlid(isOpen ? null : c.ulid)}
                >
                  {isOpen ? 'Hide details' : 'Show details'}
                </button>
              )}
              {isOpen && (
                <dl className="timeline__details">
                  {c.value_given && (<><dt>Value given</dt><dd>{c.value_given}</dd></>)}
                  {c.value_received && (<><dt>Value received</dt><dd>{c.value_received}</dd></>)}
                  {c.follow_up && (<><dt>Follow-up</dt><dd>{c.follow_up}</dd></>)}
                </dl>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ChannelGlyph({ channel }: { channel: ContactLog['channel'] }) {
  // Single-glyph mark — a flat circle with a 2-char abbreviation. Keeps
  // us free of external icon dependencies while staying inside the brand.
  const map: Record<string, string> = {
    email: 'M',
    call: 'C',
    coffee: 'cf',
    event: 'E',
    inmail: 'in',
    message: 'ms',
    other: '·',
  };
  return <span className="timeline__glyph">{map[channel] ?? channel.charAt(0).toUpperCase()}</span>;
}

import type { Partner } from '../../lib/types';
import StatusPill from '../ui/StatusPill';
import { formatAbsoluteDate, formatRelativeDate } from '../../lib/formatting';
import './PartnerCard.css';

export default function PartnerCard({ partner }: { partner: Partner }) {
  return (
    <a className="partner-card" href={`/partners/${partner.ulid}`}>
      <header className="partner-card__head">
        <h3 className="partner-card__name">{partner.name}</h3>
        <StatusPill state={partner.relationship_state} />
      </header>
      <p className="partner-card__role">
        {[partner.title, partner.practice, partner.seniority].filter(Boolean).join(' · ') || ' '}
      </p>
      <dl className="partner-card__facts">
        <dt>Last contact</dt>
        <dd>
          {partner.last_contact_date
            ? <>
                <span>{formatAbsoluteDate(partner.last_contact_date)}</span>
                <span className="partner-card__muted"> · {formatRelativeDate(partner.last_contact_date)}</span>
              </>
            : <span className="partner-card__muted">no record</span>}
        </dd>
        {partner.next_touch_date && (
          <>
            <dt>Next touch</dt>
            <dd>{formatAbsoluteDate(partner.next_touch_date)}{partner.next_touch_topic ? ` · ${partner.next_touch_topic}` : ''}</dd>
          </>
        )}
      </dl>
    </a>
  );
}

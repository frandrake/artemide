import type { Firm } from '../../lib/types';
import Badge from '../ui/Badge';
import StatusPill from '../ui/StatusPill';
import './FirmCard.css';

export default function FirmCard({ firm }: { firm: Firm }) {
  return (
    <a className="firm-card" href={`/firms/${firm.ulid}`}>
      <h3 className="firm-card__name">{firm.name}</h3>
      <div className="firm-card__meta">
        <Badge tone="neutral">{firm.tier}</Badge>
        {firm.region && <Badge tone="neutral">{firm.region}</Badge>}
        <StatusPill state={firm.relationship_state} />
      </div>
      {firm.primary_focus && (
        <p className="firm-card__focus">{firm.primary_focus}</p>
      )}
    </a>
  );
}

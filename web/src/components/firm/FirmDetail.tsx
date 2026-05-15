import { useEffect, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { ContactLog, Firm, Partner } from '../../lib/types';
import StatusPill from '../ui/StatusPill';
import Badge from '../ui/Badge';
import Button from '../ui/Button';
import EmptyState from '../ui/EmptyState';
import Skeleton from '../ui/Skeleton';
import PartnerCard from '../partner/PartnerCard';
import Timeline from './Timeline';
import EditFirmModal from './EditFirmModal';
import { formatAbsoluteDate } from '../../lib/formatting';
import './FirmDetail.css';

function ulidFromPath(): string | null {
  if (typeof window === 'undefined') return null;
  const match = window.location.pathname.match(/^\/firms\/([0-9A-HJKMNP-TV-Z]{26})\/?$/i);
  return match ? match[1].toUpperCase() : null;
}

export default function FirmDetail() {
  const [ulid, setUlid] = useState<string | null>(() => ulidFromPath());
  useEffect(() => { setUlid(ulidFromPath()); }, []);

  const firm = useFetch<Firm>(ulid ? `/api/v1/firms/${ulid}` : null);
  const partners = useFetch<Partner[]>(ulid ? `/api/v1/partners?firm_ulid=${ulid}` : null);
  const contacts = useFetch<ContactLog[]>(ulid ? `/api/v1/contacts?firm_ulid=${ulid}&limit=50` : null);

  const [showEditModal, setShowEditModal] = useState(false);

  if (!ulid) {
    return <EmptyState title="Not found" description="No firm ULID in URL." />;
  }
  if (firm.error) {
    return <EmptyState title="Couldn't load firm" description={firm.error} />;
  }

  const ninetyDayCount = contactsLast90Days(contacts.data ?? []);

  return (
    <div className="firm-detail">
      <section className="firm-detail__header">
        {firm.loading || !firm.data ? (
          <>
            <Skeleton width="50%" height={40} />
            <Skeleton width="30%" height={16} />
          </>
        ) : (
          <>
            <div className="firm-detail__header-top">
              <h1 className="firm-detail__name">{firm.data.name}</h1>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowEditModal(true)}
              >
                Edit firm
              </Button>
            </div>
            <div className="firm-detail__meta">
              <Badge tone="neutral">{firm.data.tier}</Badge>
              {firm.data.region && <Badge tone="neutral">{firm.data.region}</Badge>}
              <StatusPill state={firm.data.relationship_state} />
            </div>
            {firm.data.notes_summary && (
              <p className="firm-detail__notes">{firm.data.notes_summary}</p>
            )}
          </>
        )}
      </section>

      <section className="firm-detail__body">
        <div className="firm-detail__partners">
          <h2 className="firm-detail__h2">Partners</h2>
          {partners.loading && <Skeleton width="100%" height={160} />}
          {partners.data && partners.data.length === 0 && (
            <EmptyState title="No partners yet" description="Add a partner to start logging contact." />
          )}
          {partners.data && partners.data.length > 0 && (
            <div className="firm-detail__partner-grid">
              {partners.data.map((p) => <PartnerCard key={p.ulid} partner={p} />)}
            </div>
          )}
        </div>

        <aside className="firm-detail__stats">
          <h2 className="firm-detail__h2">At a glance</h2>
          <dl className="firm-detail__stat-list">
            <dt>Total partners</dt>
            <dd>{partners.data?.length ?? '—'}</dd>
            <dt>Contacts (last 90d)</dt>
            <dd>{ninetyDayCount}</dd>
            <dt>Last contact</dt>
            <dd>{lastContactDateLabel(partners.data ?? [])}</dd>
          </dl>
        </aside>
      </section>

      <section className="firm-detail__timeline">
        <h2 className="firm-detail__h2">Contact timeline</h2>
        {contacts.loading && <Skeleton width="100%" height={120} />}
        {contacts.data && <Timeline contacts={contacts.data} />}
      </section>

      {firm.data && (
        <EditFirmModal
          firm={firm.data}
          isOpen={showEditModal}
          onClose={() => setShowEditModal(false)}
          onSaved={() => { setShowEditModal(false); firm.refresh(); }}
          onDeleteRequest={() => { /* Phase 3: wire DeleteConfirmModal */ }}
        />
      )}
    </div>
  );
}

function contactsLast90Days(contacts: ContactLog[]): number {
  if (contacts.length === 0) return 0;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 90);
  return contacts.filter((c) => new Date(c.contact_date) >= cutoff).length;
}

function lastContactDateLabel(partners: Partner[]): string {
  const dates = partners
    .map((p) => p.last_contact_date)
    .filter((d): d is string => Boolean(d))
    .map((d) => new Date(d).getTime());
  if (dates.length === 0) return '—';
  return formatAbsoluteDate(new Date(Math.max(...dates)));
}

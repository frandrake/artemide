import { useEffect, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiDelete, apiPost, ApiError } from '../../lib/api';
import type { ContactLog, Firm, Partner } from '../../lib/types';
import StatusPill from '../ui/StatusPill';
import Badge from '../ui/Badge';
import Button from '../ui/Button';
import EmptyState from '../ui/EmptyState';
import Skeleton from '../ui/Skeleton';
import PartnerCard from '../partner/PartnerCard';
import Timeline from './Timeline';
import EditFirmModal from './EditFirmModal';
import DeleteConfirmModal from '../shared/DeleteConfirmModal';
import RestoreConfirmModal from '../shared/RestoreConfirmModal';
import Toast from '../shared/Toast';
import { formatAbsoluteDate, formatRelativeDate } from '../../lib/formatting';
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

  // Active partners always fetched; deleted fetched only when toggle is on.
  const [showDeletedPartners, setShowDeletedPartners] = useState(false);
  const activePartners = useFetch<Partner[]>(ulid ? `/api/v1/partners?firm_ulid=${ulid}` : null);
  const allPartners = useFetch<Partner[]>(
    ulid && showDeletedPartners ? `/api/v1/partners?firm_ulid=${ulid}&include_deleted=true` : null
  );
  const deletedPartners = allPartners.data?.filter((p) => !!p.deleted_at) ?? [];

  const contacts = useFetch<ContactLog[]>(ulid ? `/api/v1/contacts?firm_ulid=${ulid}&limit=50` : null);

  // Edit modal
  const [showEditModal, setShowEditModal] = useState(false);

  // Delete firm modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Restore partner modal
  const [restorePartner, setRestorePartner] = useState<Partner | null>(null);
  const [isRestoringPartner, setIsRestoringPartner] = useState(false);
  const [restorePartnerError, setRestorePartnerError] = useState<string | undefined>(undefined);

  if (!ulid) {
    return <EmptyState title="Not found" description="No firm ULID in URL." />;
  }
  if (firm.error) {
    return <EmptyState title="Couldn't load firm" description={firm.error} />;
  }

  const ninetyDayCount = contactsLast90Days(contacts.data ?? []);
  const activePartnerCount = activePartners.data?.length ?? 0;

  async function handleDeleteFirm() {
    if (!ulid) return;
    setIsDeleting(true);
    try {
      await apiDelete(`/api/v1/firms/${ulid}`);
      window.location.assign('/firms');
    } catch (e) {
      setIsDeleting(false);
      setShowDeleteModal(false);
      const msg = e instanceof ApiError ? e.message : 'Delete failed.';
      setToast(msg);
    }
  }

  async function handleRestorePartnerConfirm() {
    if (!restorePartner) return;
    setIsRestoringPartner(true);
    setRestorePartnerError(undefined);
    try {
      await apiPost(`/api/v1/partners/${restorePartner.ulid}/restore`);
      setRestorePartner(null);
      await activePartners.refresh();
      await allPartners.refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setRestorePartnerError(e.message);
      } else {
        setRestorePartner(null);
        setToast(e instanceof ApiError ? e.message : 'Restore failed.');
      }
    } finally {
      setIsRestoringPartner(false);
    }
  }

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
          <div className="firm-detail__partners-header">
            <h2 className="firm-detail__h2">Partners</h2>
            <button
              type="button"
              className={`firm-detail__deleted-toggle${showDeletedPartners ? ' is-active' : ''}`}
              onClick={() => setShowDeletedPartners((v) => !v)}
            >
              {showDeletedPartners ? 'Hide deleted partners' : 'Show deleted partners'}
            </button>
          </div>

          {activePartners.loading && <Skeleton width="100%" height={160} />}
          {activePartners.data && activePartners.data.length === 0 && (
            <EmptyState title="No partners yet" description="Add a partner to start logging contact." />
          )}
          {activePartners.data && activePartners.data.length > 0 && (
            <div className="firm-detail__partner-grid">
              {activePartners.data.map((p) => <PartnerCard key={p.ulid} partner={p} />)}
            </div>
          )}

          {showDeletedPartners && (
            <div className="firm-detail__deleted-partners">
              {allPartners.loading && <Skeleton width="100%" height={80} />}
              {deletedPartners.length > 0 && (
                <>
                  <p className="firm-detail__deleted-label">DELETED PARTNERS</p>
                  <div className="firm-detail__partner-grid">
                    {deletedPartners.map((p) => (
                      <DeletedPartnerCard
                        key={p.ulid}
                        partner={p}
                        onRestore={() => { setRestorePartnerError(undefined); setRestorePartner(p); }}
                      />
                    ))}
                  </div>
                </>
              )}
              {!allPartners.loading && deletedPartners.length === 0 && (
                <p className="firm-detail__deleted-empty">No deleted partners.</p>
              )}
            </div>
          )}
        </div>

        <aside className="firm-detail__stats">
          <h2 className="firm-detail__h2">At a glance</h2>
          <dl className="firm-detail__stat-list">
            <dt>Total partners</dt>
            <dd>{activePartners.data?.length ?? '—'}</dd>
            <dt>Contacts (last 90d)</dt>
            <dd>{ninetyDayCount}</dd>
            <dt>Last contact</dt>
            <dd>{lastContactDateLabel(activePartners.data ?? [])}</dd>
          </dl>
        </aside>
      </section>

      <section className="firm-detail__timeline">
        <h2 className="firm-detail__h2">Contact timeline</h2>
        {contacts.loading && <Skeleton width="100%" height={120} />}
        {contacts.data && <Timeline contacts={contacts.data} />}
      </section>

      {/* Edit firm modal */}
      {firm.data && (
        <EditFirmModal
          firm={firm.data}
          isOpen={showEditModal}
          onClose={() => setShowEditModal(false)}
          onSaved={() => { setShowEditModal(false); firm.refresh(); }}
          onDeleteRequest={() => { setShowEditModal(false); setShowDeleteModal(true); }}
        />
      )}

      {/* Delete firm confirm */}
      <DeleteConfirmModal
        entityType="firm"
        entityName={firm.data?.name ?? ''}
        partnerCount={activePartnerCount}
        isOpen={showDeleteModal}
        isDeleting={isDeleting}
        onConfirm={handleDeleteFirm}
        onCancel={() => setShowDeleteModal(false)}
      />

      {/* Restore partner confirm */}
      <RestoreConfirmModal
        entityType="partner"
        entityName={restorePartner?.name ?? ''}
        isOpen={!!restorePartner}
        isRestoring={isRestoringPartner}
        error={restorePartnerError}
        onConfirm={handleRestorePartnerConfirm}
        onCancel={() => { setRestorePartner(null); setRestorePartnerError(undefined); }}
      />

      {toast && <Toast message={toast} tone="error" onDismiss={() => setToast(null)} />}
    </div>
  );
}

function DeletedPartnerCard({ partner, onRestore }: { partner: Partner; onRestore: () => void }) {
  const deletedAgo = partner.deleted_at ? formatRelativeDate(partner.deleted_at) : '';
  return (
    <div className="partner-card partner-card--deleted">
      <header className="partner-card__head">
        <h3 className="partner-card__name partner-card__name--deleted">{partner.name}</h3>
      </header>
      <p className="partner-card__role">
        {[partner.title, partner.practice, partner.seniority].filter(Boolean).join(' · ') || ' '}
      </p>
      <p className="partner-card__deleted-note">deleted {deletedAgo}</p>
      <button type="button" className="partner-card__restore-btn" onClick={onRestore}>
        Restore
      </button>
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

import { useEffect, useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPatch, apiDelete, ApiError } from '../../lib/api';
import type { ContactLog, Note, OutreachDraftRecord, Partner } from '../../lib/types';
import DraftEditor from '../outreach/DraftEditor';
import StatusPill from '../ui/StatusPill';
import Button from '../ui/Button';
import EmptyState from '../ui/EmptyState';
import Skeleton from '../ui/Skeleton';
import Textarea from '../ui/Textarea';
import Timeline from '../firm/Timeline';
import LogContactForm from './LogContactForm';
import EditPartnerModal from './EditPartnerModal';
import DeleteConfirmModal from '../shared/DeleteConfirmModal';
import Toast from '../shared/Toast';
import {
  formatAbsoluteDate, formatRelativeDate,
} from '../../lib/formatting';
import './PartnerDetail.css';

function ulidFromPath(): string | null {
  if (typeof window === 'undefined') return null;
  const match = window.location.pathname.match(/^\/partners\/([0-9A-HJKMNP-TV-Z]{26})\/?$/i);
  return match ? match[1].toUpperCase() : null;
}

function parseFollowUps(raw: string | null): string[] {
  if (!raw) return [];
  try { const parsed = JSON.parse(raw); return Array.isArray(parsed) ? parsed.map(String) : []; } catch { return []; }
}

export default function PartnerDetail() {
  const [ulid, setUlid] = useState<string | null>(() => ulidFromPath());
  useEffect(() => { setUlid(ulidFromPath()); }, []);

  const partner = useFetch<Partner>(ulid ? `/api/v1/partners/${ulid}` : null);

  const firmName = partner.data?.firm_name ?? null;
  const firmUlid = partner.data?.firm_ulid ?? null;
  const contacts = useFetch<ContactLog[]>(ulid ? `/api/v1/contacts?partner_ulid=${ulid}&limit=100` : null);
  const notes = useFetch<Note[]>(ulid ? `/api/v1/notes?entity_type=partner&entity_ulid=${ulid}` : null);

  const [logOpen, setLogOpen] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const followUps = useMemo(() => parseFollowUps(partner.data?.follow_ups_outstanding ?? null), [partner.data]);

  if (!ulid) return <EmptyState title="Not found" description="No partner ULID in URL." />;
  if (partner.error) return <EmptyState title="Couldn't load partner" description={partner.error} />;

  return (
    <div className="partner-detail">
      <section className="partner-detail__header">
        {partner.loading || !partner.data ? (
          <>
            <Skeleton width="50%" height={48} />
            <Skeleton width="30%" height={16} />
          </>
        ) : (
          <>
            <div className="partner-detail__title-row">
              <div>
                <h1 className="partner-detail__name">{partner.data.name}</h1>
                <p className="partner-detail__sub">
                  {firmUlid && firmName
                    ? <a className="partner-detail__firm-link" href={`/firms/${firmUlid}`}>{firmName}</a>
                    : '…'}
                  {partner.data.practice ? ` · ${partner.data.practice}` : ''}
                </p>
              </div>
              <div className="partner-detail__title-actions">
                <StatusPill state={partner.data.relationship_state} />
                <Button
                  variant="secondary"
                  size="md"
                  onClick={() => setShowEditModal(true)}
                >
                  Edit partner
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  onClick={() => setLogOpen(true)}
                  disabled={!firmName}
                >
                  Log contact
                </Button>
              </div>
            </div>
          </>
        )}
      </section>

      <section className="partner-detail__body">
        <div className="partner-detail__facts">
          <h2 className="partner-detail__h2">Profile</h2>
          {partner.data && <PartnerFacts partner={partner.data} />}
          {partner.data && <PartnerIntelligencePanel partner={partner.data} />}
        </div>

        <aside className="partner-detail__followups">
          <h2 className="partner-detail__h2">Follow-ups</h2>
          <FollowUps
            partner={partner.data}
            items={followUps}
            onSaved={partner.refresh}
          />
        </aside>
      </section>

      <section className="partner-detail__drafts">
        <h2 className="partner-detail__h2">Drafts</h2>
        {partner.data && <PartnerDrafts partner={partner.data} />}
      </section>

      <section className="partner-detail__timeline">
        <h2 className="partner-detail__h2">Contact timeline</h2>
        {contacts.loading && <Skeleton width="100%" height={120} />}
        {contacts.data && <Timeline contacts={contacts.data} />}
      </section>

      <section className="partner-detail__notes">
        <h2 className="partner-detail__h2">Notes</h2>
        {partner.data && (
          <NotesPanel
            entityType="partner"
            entityUlid={partner.data.ulid}
            notes={notes.data ?? []}
            loading={notes.loading}
            onSaved={notes.refresh}
          />
        )}
      </section>

      {firmName && partner.data && (
        <LogContactForm
          open={logOpen}
          onClose={() => setLogOpen(false)}
          firmName={firmName}
          partnerName={partner.data.name}
          onLogged={() => { contacts.refresh(); partner.refresh(); }}
        />
      )}

      {partner.data && firmName && (
        <EditPartnerModal
          partner={partner.data}
          firmName={firmName}
          isOpen={showEditModal}
          onClose={() => setShowEditModal(false)}
          onSaved={() => { setShowEditModal(false); partner.refresh(); }}
          onDeleteRequest={() => { setShowEditModal(false); setShowDeleteModal(true); }}
        />
      )}

      <DeleteConfirmModal
        entityType="partner"
        entityName={partner.data?.name ?? ''}
        isOpen={showDeleteModal}
        isDeleting={isDeleting}
        onConfirm={async () => {
          if (!ulid) return;
          setIsDeleting(true);
          try {
            await apiDelete(`/api/v1/partners/${ulid}`);
            if (firmUlid) {
              window.location.assign(`/firms/${firmUlid}`);
            } else {
              window.location.assign('/firms');
            }
          } catch (e) {
            setIsDeleting(false);
            setShowDeleteModal(false);
            setToast(e instanceof ApiError ? e.message : 'Delete failed.');
          }
        }}
        onCancel={() => setShowDeleteModal(false)}
      />

      {toast && <Toast message={toast} tone="error" onDismiss={() => setToast(null)} />}
    </div>
  );
}

// ---------- read-only facts panel ----------

function PartnerFacts({ partner }: { partner: Partner }) {
  return (
    <dl className="partner-detail__fact-list">
      <Fact label="Title" value={partner.title} />
      <Fact label="Practice" value={partner.practice} />
      <Fact label="Seniority" value={partner.seniority} />
      <Fact label="Location" value={partner.location} />
      <Fact label="Introduced via" value={partner.introduced_via} />
      <Fact label="Email" value={partner.email} />
      <Fact label="LinkedIn" value={partner.linkedin_url} />
      <Fact label="Last contact" value={formatDateField(partner.last_contact_date)} />
      <Fact label="Next planned touch" value={formatDateField(partner.next_touch_date)} />
      <Fact label="Next planned topic" value={partner.next_touch_topic} />
      <Fact label="Notes summary" value={partner.notes_summary} />
    </dl>
  );
}

function PartnerIntelligencePanel({ partner }: { partner: Partner }) {
  const chips: { label: string; value: string | null | undefined }[] = [
    { label: 'Strategic relevance', value: partner.strategic_relevance },
    { label: 'Outreach stage', value: partner.outreach_stage },
  ];
  const visibleChips = chips.filter(c => c.value);
  if (partner.ned_gateway) visibleChips.push({ label: 'NED gateway', value: 'Yes' });

  const prose: { label: string; value: string | null | undefined }[] = [
    { label: 'Practice focus', value: partner.practice_focus },
    { label: 'Warm intro angle', value: partner.warm_intro_angle },
    { label: 'Thought leadership', value: partner.thought_leadership },
    { label: 'Prior career', value: partner.prior_career },
  ].filter(p => p.value);

  if (visibleChips.length === 0 && prose.length === 0) return null;

  return (
    <div className="partner-detail__intel">
      {visibleChips.length > 0 && (
        <div className="partner-detail__intel-chips">
          {visibleChips.map(c => (
            <span key={c.label} className="partner-detail__intel-chip">
              <strong>{c.label}:</strong> {c.value}
            </span>
          ))}
        </div>
      )}
      {prose.map(p => (
        <div key={p.label} className="partner-detail__intel-prose-row">
          <span className="partner-detail__intel-label">{p.label}</span>
          <span className="partner-detail__intel-value">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

function PartnerDrafts({ partner }: { partner: Partner }) {
  const drafts = useFetch<OutreachDraftRecord[]>(`/api/v1/outreach/drafts?partner_ulid=${partner.ulid}`);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingUlid, setEditingUlid] = useState<string | null>(null);

  function openNew() {
    setEditingUlid(null);
    setEditorOpen(true);
  }
  function openExisting(ulid: string) {
    setEditingUlid(ulid);
    setEditorOpen(true);
  }

  return (
    <div className="partner-drafts">
      <div className="partner-drafts__header">
        <Button variant="secondary" size="sm" onClick={openNew}>+ New draft</Button>
      </div>
      {drafts.loading && <Skeleton width="100%" height={48} />}
      {drafts.data && drafts.data.length === 0 && (
        <p className="partner-drafts__empty">No drafts yet.</p>
      )}
      {drafts.data && drafts.data.length > 0 && (
        <ul className="partner-drafts__list">
          {drafts.data.map(d => (
            <li key={d.ulid} className="partner-drafts__row">
              <button
                type="button"
                className="partner-drafts__row-button"
                onClick={() => openExisting(d.ulid)}
              >
                <span className={`partner-drafts__status partner-drafts__status--${d.status}`}>{d.status}</span>
                <span className="partner-drafts__channel">{d.channel}</span>
                <span className="partner-drafts__subject">{d.subject || '(no subject)'}</span>
                <span className="partner-drafts__version">v{d.version}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {editorOpen && (
        <DraftEditor
          partnerUlid={partner.ulid}
          draftUlid={editingUlid}
          isOpen={editorOpen}
          onClose={() => setEditorOpen(false)}
          onSaved={() => { setEditorOpen(false); drafts.refresh(); }}
        />
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>
        {value
          ? <span className="partner-detail__value">{value}</span>
          : <em className="partner-detail__placeholder">—</em>}
      </dd>
    </>
  );
}

function formatDateField(d: string | null | undefined): string | null {
  if (!d) return null;
  return `${formatAbsoluteDate(d)} (${formatRelativeDate(d)})`;
}

// ---------- follow-ups list (with optimistic check-off) ----------

interface FollowUpsProps {
  partner: Partner | null;
  items: string[];
  onSaved: () => Promise<void>;
}

function FollowUps({ partner, items, onSaved }: FollowUpsProps) {
  const [localItems, setLocalItems] = useState<string[]>(items);
  const [draft, setDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync from parent when partner data reloads.
  useEffect(() => { setLocalItems(items); }, [items]);

  async function save(next: string[]) {
    if (!partner) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiPatch(`/api/v1/partners/${partner.ulid}`, { follow_ups_outstanding: next });
      await onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed.');
    } finally {
      setSubmitting(false);
    }
  }

  async function add() {
    if (!draft.trim()) return;
    await save([...localItems, draft.trim()]);
    setDraft('');
  }

  async function removeAt(i: number) {
    const remaining = localItems.filter((_, idx) => idx !== i);
    // Optimistic: update display immediately.
    setLocalItems(remaining);
    try {
      if (!partner) return;
      setSubmitting(true);
      setError(null);
      await apiPatch<Partner>(`/api/v1/partners/${partner.ulid}`, { follow_ups_outstanding: remaining });
      await onSaved();
    } catch (e) {
      // Restore on failure.
      setLocalItems(items);
      setError(e instanceof Error ? e.message : 'Save failed.');
    } finally {
      setSubmitting(false);
    }
  }

  if (!partner) return <Skeleton width="100%" height={80} />;
  return (
    <div className="follow-ups">
      {localItems.length === 0 && <p className="follow-ups__empty">No outstanding follow-ups.</p>}
      <ul className="follow-ups__list">
        {localItems.map((item, i) => (
          <li key={i} className="follow-ups__row">
            <span>{item}</span>
            <button
              type="button"
              className="follow-ups__remove"
              aria-label={`Resolve follow-up: ${item}`}
              disabled={submitting}
              onClick={() => removeAt(i)}
            >Done</button>
          </li>
        ))}
      </ul>
      <div className="follow-ups__add">
        <input
          type="text"
          placeholder="Add follow-up"
          value={draft}
          onChange={(e) => setDraft(e.currentTarget.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
        />
        <Button variant="secondary" size="sm" type="button" onClick={add} disabled={!draft.trim() || submitting}>
          Add
        </Button>
      </div>
      {error && <p className="follow-ups__error" role="alert">{error}</p>}
    </div>
  );
}

// ---------- notes panel ----------

interface NotesPanelProps {
  entityType: 'partner' | 'firm';
  entityUlid: string;
  notes: Note[];
  loading: boolean;
  onSaved: () => Promise<void>;
}

function NotesPanel({ entityType, entityUlid, notes, loading, onSaved }: NotesPanelProps) {
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (!body.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await import('../../lib/api').then(({ apiPost }) =>
        apiPost('/api/v1/notes', { entity_type: entityType, entity_ulid: entityUlid, body: body.trim() })
      );
      await onSaved();
      setBody('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="notes-panel">
      {loading && <Skeleton width="100%" height={80} />}
      <ul className="notes-panel__list">
        {notes.map((n) => (
          <li key={n.ulid} className="notes-panel__row">
            <p className="notes-panel__body">{n.body}</p>
            <span className="notes-panel__date">{formatAbsoluteDate(n.created_at)}</span>
          </li>
        ))}
        {!loading && notes.length === 0 && (
          <li className="notes-panel__empty">No notes yet.</li>
        )}
      </ul>
      <div className="notes-panel__add">
        <Textarea
          label="Add a note"
          rows={3}
          value={body}
          onChange={(e) => setBody(e.currentTarget.value)}
        />
        <Button variant="secondary" size="sm" type="button" onClick={add} disabled={!body.trim() || submitting}>
          Save note
        </Button>
      </div>
      {error && <p className="notes-panel__error" role="alert">{error}</p>}
    </div>
  );
}

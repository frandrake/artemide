import { useEffect, useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPatch, apiPost, ApiError } from '../../lib/api';
import type { ContactLog, Note, Partner } from '../../lib/types';
import StatusPill from '../ui/StatusPill';
import Button from '../ui/Button';
import EmptyState from '../ui/EmptyState';
import Skeleton from '../ui/Skeleton';
import Textarea from '../ui/Textarea';
import Timeline from '../firm/Timeline';
import LogContactForm from './LogContactForm';
import {
  formatAbsoluteDate, formatRelativeDate,
} from '../../lib/formatting';
import './PartnerDetail.css';

function ulidFromPath(): string | null {
  if (typeof window === 'undefined') return null;
  const match = window.location.pathname.match(/^\/partners\/([0-9A-HJKMNP-TV-Z]{26})\/?$/i);
  return match ? match[1].toUpperCase() : null;
}

export default function PartnerDetail() {
  const [ulid, setUlid] = useState<string | null>(() => ulidFromPath());
  useEffect(() => { setUlid(ulidFromPath()); }, []);

  const partner = useFetch<Partner>(ulid ? `/api/v1/partners/${ulid}` : null);

  // Firm name + ulid arrive inlined with the partner GET response.
  const firmName = partner.data?.firm_name ?? null;
  const firmUlid = partner.data?.firm_ulid ?? null;
  const contacts = useFetch<ContactLog[]>(ulid ? `/api/v1/contacts?partner_ulid=${ulid}&limit=100` : null);
  const notes = useFetch<Note[]>(ulid ? `/api/v1/notes?entity_type=partner&entity_ulid=${ulid}` : null);

  const [logOpen, setLogOpen] = useState(false);

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
                  variant="primary"
                  size="md"
                  onClick={() => setLogOpen(true)}
                  disabled={!firmName}
                >Log contact</Button>
              </div>
            </div>
          </>
        )}
      </section>

      <section className="partner-detail__body">
        <div className="partner-detail__facts">
          <h2 className="partner-detail__h2">Profile</h2>
          {partner.data && <PartnerFacts partner={partner.data} onSaved={partner.refresh} />}
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
    </div>
  );
}

function parseFollowUps(raw: string | null): string[] {
  if (!raw) return [];
  try { const parsed = JSON.parse(raw); return Array.isArray(parsed) ? parsed.map(String) : []; } catch { return []; }
}

// ---------- inline-editable facts panel ----------

function PartnerFacts({ partner, onSaved }: { partner: Partner; onSaved: () => Promise<void> }) {
  return (
    <dl className="partner-detail__fact-list">
      <Row label="Title" partner={partner} field="title" onSaved={onSaved} />
      <Row label="Practice" partner={partner} field="practice" onSaved={onSaved} />
      <Row label="Seniority" partner={partner} field="seniority" onSaved={onSaved} />
      <Row label="Email" partner={partner} field="email" onSaved={onSaved} type="email" />
      <Row label="LinkedIn" partner={partner} field="linkedin_url" onSaved={onSaved} type="url" />
      <Row label="Last contact" partner={partner} field="last_contact_date" readOnly />
      <Row label="Next planned touch" partner={partner} field="next_touch_date" onSaved={onSaved} type="date" />
      <Row label="Next planned topic" partner={partner} field="next_touch_topic" onSaved={onSaved} />
      <Row label="Notes summary" partner={partner} field="notes_summary" onSaved={onSaved} />
      <Row label="State" partner={partner} field="relationship_state" onSaved={onSaved} kind="state" />
    </dl>
  );
}

interface RowProps {
  label: string;
  partner: Partner;
  field: keyof Partner;
  type?: 'text' | 'date' | 'email' | 'url';
  kind?: 'state';
  readOnly?: boolean;
  onSaved?: () => Promise<void>;
}

function Row({ label, partner, field, type = 'text', kind, readOnly, onSaved }: RowProps) {
  const value = partner[field];
  const display = formatValue(field, value);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(value == null ? '' : String(value));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!onSaved) return;
    setBusy(true);
    setError(null);
    try {
      // Only PATCH the field. For follow_ups/state we go through dedicated endpoints if needed.
      const body: Record<string, unknown> = {};
      if (field === 'relationship_state') {
        // Use PATCH /api/v1/firms/{ulid} is for firms only; partner state
        // is part of upsert. Use the partners PATCH endpoint for date+topic only;
        // relationship_state requires upsert via POST. Skip for now.
        setError('Edit state via Log contact (advance) or upsert.');
        setBusy(false);
        return;
      } else if (field === 'next_touch_date' || field === 'next_touch_topic') {
        body[field] = draft || null;
      } else {
        setError('Inline edit not supported for this field yet.');
        setBusy(false);
        return;
      }
      await apiPatch(`/api/v1/partners/${partner.ulid}`, body);
      await onSaved?.();
      setEditing(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e instanceof Error ? e.message : 'Save failed.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <dt>{label}</dt>
      <dd>
        {!editing && (
          <span
            className={`partner-detail__value${readOnly ? '' : ' is-editable'}`}
            onClick={() => !readOnly && onSaved && setEditing(true)}
            onKeyDown={(e) => { if (!readOnly && onSaved && e.key === 'Enter') setEditing(true); }}
            tabIndex={readOnly ? -1 : 0}
            role={readOnly ? undefined : 'button'}
            aria-label={readOnly ? undefined : `Edit ${label}`}
          >
            {display || <em className="partner-detail__placeholder">add</em>}
          </span>
        )}
        {editing && (
          <span className="partner-detail__edit">
            <input
              type={type}
              autoFocus
              value={draft}
              disabled={busy}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={save}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); save(); }
                if (e.key === 'Escape') { setEditing(false); setDraft(value == null ? '' : String(value)); }
              }}
            />
            {error && <span className="partner-detail__edit-error">{error}</span>}
          </span>
        )}
      </dd>
    </>
  );
}

function formatValue(field: keyof Partner, value: Partner[keyof Partner]): string {
  if (value == null || value === '') return '';
  if (field === 'last_contact_date' || field === 'next_touch_date') {
    const s = String(value);
    return `${formatAbsoluteDate(s)} (${formatRelativeDate(s)})`;
  }
  return String(value);
}

// ---------- follow-ups list ----------

interface FollowUpsProps {
  partner: Partner | null;
  items: string[];
  onSaved: () => Promise<void>;
}

function FollowUps({ partner, items, onSaved }: FollowUpsProps) {
  const [draft, setDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(next: string[]) {
    if (!partner) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiPatch(`/api/v1/partners/${partner.ulid}`, { follow_ups: next });
      await onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed.');
    } finally {
      setSubmitting(false);
    }
  }

  async function add() {
    if (!draft.trim()) return;
    await save([...items, draft.trim()]);
    setDraft('');
  }
  async function removeAt(i: number) {
    await save(items.filter((_, idx) => idx !== i));
  }

  if (!partner) return <Skeleton width="100%" height={80} />;
  return (
    <div className="follow-ups">
      {items.length === 0 && <p className="follow-ups__empty">No outstanding follow-ups.</p>}
      <ul className="follow-ups__list">
        {items.map((item, i) => (
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
      await apiPost('/api/v1/notes', {
        entity_type: entityType,
        entity_ulid: entityUlid,
        body: body.trim(),
      });
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

import { useEffect, useMemo, useState } from 'react';
import { apiGet, apiPost, ApiError } from '../../lib/api';
import type { Firm, Note, Partner } from '../../lib/types';
import Button from '../ui/Button';
import Dialog from '../ui/Dialog';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import Skeleton from '../ui/Skeleton';
import { formatAbsoluteDate } from '../../lib/formatting';
import './NotesInbox.css';

interface NoteWithLabel extends Note { label: string; href: string }

export default function NotesInbox() {
  const [notes, setNotes] = useState<NoteWithLabel[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'firm' | 'partner'>('all');
  const [addOpen, setAddOpen] = useState(false);
  const [firms, setFirms] = useState<Firm[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [allFirms, allPartners] = await Promise.all([
        apiGet<Firm[]>('/api/v1/firms?include_deleted=false'),
        apiGet<Partner[]>('/api/v1/partners'),
      ]);
      setFirms(allFirms);
      setPartners(allPartners);

      const firmNotes = await Promise.all(
        allFirms.map((f) => apiGet<Note[]>(`/api/v1/notes?entity_type=firm&entity_ulid=${f.ulid}`)
          .then((ns) => ns.map((n) => ({ ...n, label: f.name, href: `/firms/${f.ulid}` })))),
      );
      const partnerNotes = await Promise.all(
        allPartners.map((p) => apiGet<Note[]>(`/api/v1/notes?entity_type=partner&entity_ulid=${p.ulid}`)
          .then((ns) => ns.map((n) => ({ ...n, label: p.name, href: `/partners/${p.ulid}` })))),
      );
      const merged = ([] as NoteWithLabel[])
        .concat(...firmNotes, ...partnerNotes)
        .sort((a, b) => b.created_at.localeCompare(a.created_at));
      setNotes(merged);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to load notes.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  const filtered = useMemo(() => {
    if (!notes) return null;
    if (filter === 'all') return notes;
    return notes.filter((n) => n.entity_type === filter);
  }, [notes, filter]);

  return (
    <div className="notes-inbox">
      <header className="notes-inbox__head">
        <div>
          <h1>Notes inbox</h1>
          <p className="notes-inbox__sub">{notes ? `${notes.length} notes total` : ' '}</p>
        </div>
        <div className="notes-inbox__head-actions">
          <Select label="Filter" value={filter} onChange={(e) => setFilter(e.currentTarget.value as 'all' | 'firm' | 'partner')}>
            <option value="all">All</option>
            <option value="firm">Firm notes</option>
            <option value="partner">Partner notes</option>
          </Select>
        </div>
      </header>

      {loading && <Skeleton width="100%" height={160} />}
      {error && <p className="notes-inbox__error" role="alert">{error}</p>}

      {filtered && filtered.length === 0 && !loading && (
        <p className="notes-inbox__empty">No notes yet.</p>
      )}

      {filtered && filtered.length > 0 && (
        <ul className="notes-inbox__list">
          {filtered.map((n) => (
            <li className="notes-inbox__row" key={n.ulid}>
              <header className="notes-inbox__row-head">
                <a className="notes-inbox__link" href={n.href}>{n.label}</a>
                <span className="notes-inbox__type">{n.entity_type}</span>
                <span className="notes-inbox__date">{formatAbsoluteDate(n.created_at)}</span>
              </header>
              <p className="notes-inbox__body">{n.body}</p>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        className="notes-inbox__fab"
        aria-label="Add note"
        onClick={() => setAddOpen(true)}
      >+</button>

      {addOpen && (
        <AddNoteDialog
          firms={firms}
          partners={partners}
          onClose={() => setAddOpen(false)}
          onAdded={async () => { setAddOpen(false); await refresh(); }}
        />
      )}
    </div>
  );
}

function AddNoteDialog({ firms, partners, onClose, onAdded }: {
  firms: Firm[]; partners: Partner[]; onClose: () => void; onAdded: () => Promise<void>;
}) {
  const [entityType, setEntityType] = useState<'firm' | 'partner'>('partner');
  const [entityUlid, setEntityUlid] = useState<string>(partners[0]?.ulid ?? firms[0]?.ulid ?? '');
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const options = entityType === 'firm' ? firms : partners;

  async function save() {
    if (!body.trim() || !entityUlid) return;
    setSubmitting(true);
    setError(null);
    try {
      await apiPost('/api/v1/notes', {
        entity_type: entityType,
        entity_ulid: entityUlid,
        body: body.trim(),
      });
      await onAdded();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Save failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open onClose={onClose} title="Add note">
      <div className="notes-inbox__add">
        <Select
          label="Attach to"
          value={entityType}
          onChange={(e) => {
            const next = e.currentTarget.value as 'firm' | 'partner';
            setEntityType(next);
            const list = next === 'firm' ? firms : partners;
            setEntityUlid(list[0]?.ulid ?? '');
          }}
        >
          <option value="partner">Partner</option>
          <option value="firm">Firm</option>
        </Select>
        <Select
          label={entityType === 'firm' ? 'Firm' : 'Partner'}
          value={entityUlid}
          onChange={(e) => setEntityUlid(e.currentTarget.value)}
        >
          {options.map((o) => <option key={o.ulid} value={o.ulid}>{o.name}</option>)}
        </Select>
        <Textarea
          label="Note"
          rows={4}
          value={body}
          onChange={(e) => setBody(e.currentTarget.value)}
        />
        {error && <p className="notes-inbox__error" role="alert">{error}</p>}
        <div className="notes-inbox__add-actions">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="button" loading={submitting} disabled={!body.trim() || !entityUlid} onClick={save}>
            Save note
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

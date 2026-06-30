import { useMemo } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { BoardFirm } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { boardUlidFromPath, titleCase } from './helpers';
import './board.css';

export default function BoardFirmDetail() {
  const ulid = useMemo(() => boardUlidFromPath('firms'), []);
  const { data: f, loading, error } = useFetch<BoardFirm>(ulid ? `/api/v1/board/firms/${ulid}` : null);

  if (!ulid) return <p className="bd-error">Invalid URL.</p>;
  if (loading) return <Skeleton height={320} />;
  if (error) return <p className="bd-error">{error}</p>;
  if (!f) return null;

  return (
    <div className="bd-detail">
      <header className="bd-head">
        <h1>{f.name}</h1>
        <p className="bd-subhead">
          {f.firm_type ? titleCase(f.firm_type) : '—'}
          {f.tier != null ? ` · Tier ${f.tier}` : ''} · {titleCase(f.status)}
        </p>
      </header>

      <section className="bd-panel">
        <h2>Profile</h2>
        <dl className="bd-kv">
          <dt>Geography</dt><dd>{f.geography.length ? f.geography.join(', ') : '—'}</dd>
          <dt>Sectors / level</dt><dd>{f.sectors_level ?? '—'}</dd>
          <dt>AI-on-boards hook</dt><dd>{f.ai_on_boards_hook ?? '—'}</dd>
          <dt>Next action</dt><dd>{f.next_action ?? '—'}</dd>
          <dt>Source</dt><dd>{f.source_url ? <a href={f.source_url}>{f.source_url}</a> : '—'}</dd>
          <dt>Notes</dt><dd>{f.notes ?? '—'}</dd>
        </dl>
      </section>

      <section className="bd-panel">
        <h2>Contacts</h2>
        {(f.contacts?.length ?? 0) === 0 ? <p className="bd-card__sub">No contacts yet.</p> : (
          <table className="bd-table">
            <thead><tr><th>Name</th><th>Role</th><th>Relationship</th><th>Last contact</th><th></th></tr></thead>
            <tbody>
              {f.contacts!.map((c) => (
                <tr key={c.ulid}>
                  <td>{c.name}</td>
                  <td>{c.role_title ?? '—'}</td>
                  <td><span className={`bd-pill bd-pill--${c.relationship}`}>{c.relationship}</span></td>
                  <td>{c.last_contact_date ?? '—'}</td>
                  <td>{c.verify_before_send && <span className="bd-pill bd-pill--flag">verify</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

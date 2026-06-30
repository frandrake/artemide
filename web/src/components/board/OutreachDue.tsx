import { useFetch } from '../../lib/useFetch';
import type { BoardInteraction, BoardTask, BoardContact } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { titleCase } from './helpers';
import './board.css';

export default function OutreachDue() {
  const interactions = useFetch<BoardInteraction[]>('/api/v1/board/interactions/due?within_days=14');
  const tasks = useFetch<BoardTask[]>('/api/v1/board/tasks?status=open&due_within_days=14');
  const stale = useFetch<BoardContact[]>('/api/v1/board/contacts?stale=true');

  if (interactions.loading || tasks.loading || stale.loading) return <Skeleton height={280} />;
  const err = interactions.error || tasks.error || stale.error;
  if (err) return <p className="bd-error">{err}</p>;

  const noneDue =
    (interactions.data?.length ?? 0) === 0 &&
    (tasks.data?.length ?? 0) === 0 &&
    (stale.data?.length ?? 0) === 0;
  if (noneDue) {
    return <EmptyState title="Nothing due." description="No board interactions, tasks or stale contacts in the window." />;
  }

  return (
    <div className="bd-detail">
      <section className="bd-panel">
        <h2>Interactions due (14 days)</h2>
        {(interactions.data?.length ?? 0) === 0 ? <p className="bd-card__sub">None.</p> : (
          <table className="bd-table">
            <thead><tr><th>Due</th><th>Type</th><th>Summary</th><th>Next action</th></tr></thead>
            <tbody>
              {interactions.data!.map((i) => (
                <tr key={i.ulid}>
                  <td>{i.due_date ?? '—'}</td>
                  <td>{titleCase(i.interaction_type)}</td>
                  <td>{i.summary ?? '—'}</td>
                  <td>{i.next_action ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="bd-panel">
        <h2>Open tasks due (14 days)</h2>
        {(tasks.data?.length ?? 0) === 0 ? <p className="bd-card__sub">None.</p> : (
          <table className="bd-table">
            <thead><tr><th>Due</th><th>Title</th></tr></thead>
            <tbody>
              {tasks.data!.map((t) => (
                <tr key={t.ulid}><td>{t.due_date ?? '—'}</td><td>{t.title}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="bd-panel">
        <h2>Contacts to re-verify (&gt;90 days)</h2>
        {(stale.data?.length ?? 0) === 0 ? <p className="bd-card__sub">None.</p> : (
          <table className="bd-table">
            <thead><tr><th>Name</th><th>Firm</th><th>Last contact</th></tr></thead>
            <tbody>
              {stale.data!.map((c) => (
                <tr key={c.ulid}>
                  <td>{c.name} <span className="bd-pill bd-pill--flag">verify before send</span></td>
                  <td>{c.firm_name ?? '—'}</td>
                  <td>{c.last_contact_date ?? 'never'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

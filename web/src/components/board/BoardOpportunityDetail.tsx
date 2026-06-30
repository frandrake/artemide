import { useMemo } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { BoardOpportunity } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { boardUlidFromPath, titleCase, verdictTone } from './helpers';
import EvaluationForm from './EvaluationForm';
import './board.css';

export default function BoardOpportunityDetail() {
  const ulid = useMemo(() => boardUlidFromPath('opportunities'), []);
  const { data: o, loading, error, refresh } = useFetch<BoardOpportunity>(
    ulid ? `/api/v1/board/opportunities/${ulid}` : null);

  if (!ulid) return <p className="bd-error">Invalid URL.</p>;
  if (loading) return <Skeleton height={360} />;
  if (error) return <p className="bd-error">{error}</p>;
  if (!o) return null;

  const screen = o.conflict_screen;

  return (
    <div className="bd-detail">
      <header className="bd-head">
        <h1>{o.organisation}</h1>
        <p className="bd-subhead">
          {o.role ? o.role.toUpperCase() : '—'}
          {o.board_type ? ` · ${titleCase(o.board_type)}` : ''} · {titleCase(o.stage)}
        </p>
      </header>

      <section className="bd-panel">
        <h2>Details</h2>
        <dl className="bd-kv">
          <dt>Source</dt><dd>{o.source_firm_name ?? o.source_text ?? '—'}</dd>
          <dt>Chair</dt><dd>{o.chair_name ?? '—'}</dd>
          <dt>Date surfaced</dt><dd>{o.date_surfaced ?? '—'}</dd>
          <dt>Conflict cleared</dt>
          <dd><span className={`bd-pill ${o.conflict_cleared === 'yes' ? 'bd-pill--warm' : o.conflict_cleared === 'no' ? 'bd-pill--flag' : ''}`}>{o.conflict_cleared}</span></dd>
          <dt>Interest</dt><dd>{o.interest}</dd>
          <dt>Next step</dt><dd>{o.next_step ?? '—'}</dd>
        </dl>
      </section>

      <section className="bd-panel">
        <h2>Conflict screen</h2>
        {screen ? (
          <dl className="bd-kv">
            <dt>Result</dt><dd>{screen.result}</dd>
            <dt>S&amp;P competitor</dt><dd>{screen.is_sp_competitor ? 'yes' : 'no'}</dd>
            <dt>Checked</dt><dd>{screen.checked_date ?? '—'}</dd>
            <dt>Notes</dt><dd>{screen.notes ?? '—'}</dd>
          </dl>
        ) : (
          <p className="bd-card__sub">Not screened yet — record one from the Conflicts queue.</p>
        )}
      </section>

      <section className="bd-panel">
        <h2>Evaluation
          {o.eval_verdict && <span className={`bd-pill ${verdictTone(o.eval_verdict)}`} style={{ marginLeft: 8 }}>{titleCase(o.eval_verdict)}</span>}
        </h2>
        <EvaluationForm opportunityUlid={o.ulid} evaluation={o.evaluation} onSaved={refresh} />
      </section>

      <section className="bd-panel">
        <h2>Stage trail</h2>
        {(o.log?.length ?? 0) === 0 ? <p className="bd-card__sub">No events yet.</p> : (
          <table className="bd-table">
            <thead><tr><th>Date</th><th>Event</th><th>From → To</th><th>Summary</th></tr></thead>
            <tbody>
              {o.log!.map((l) => (
                <tr key={l.ulid}>
                  <td>{l.event_date}</td>
                  <td>{titleCase(l.event_type)}</td>
                  <td>{l.from_stage || l.to_stage ? `${l.from_stage ?? '—'} → ${l.to_stage ?? '—'}` : '—'}</td>
                  <td>{l.summary ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

import { useCallback, useEffect, useState } from 'react';
import './TodayCommandCenter.css';

type Workstream = 'executive' | 'board';
type TodayAction = {
  source_key: string;
  workstream: Workstream;
  action_type: string;
  entity_type: string;
  entity_ulid: string;
  title: string;
  context: string | null;
  href: string;
  due_date: string | null;
  score: number;
  reasons: string[];
  operations: Array<'open' | 'complete' | 'snooze' | 'dismiss'>;
};
type TodayPayload = {
  date: string;
  actions: TodayAction[];
  available: number;
  counts: { executive: number; board: number };
  overview: {
    live_opportunities: Array<{ workstream: Workstream; ulid: string; title: string; organisation: string; stage: string; due_date: string | null; href: string }>;
    deadlines: Array<{ source_key: string; workstream: Workstream; title: string; due_date: string; href: string }>;
    cooling_contacts: Array<{ workstream: Workstream; ulid: string; name: string; organisation: string | null; last_contact_date: string | null; href: string }>;
    metrics: { live_opportunities: number; overdue_actions: number; cooling_contacts: number };
  };
};

function inSevenDays(): string {
  const value = new Date();
  value.setDate(value.getDate() + 7);
  return value.toISOString().slice(0, 10);
}

export default function TodayCommandCenter() {
  const [data, setData] = useState<TodayPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/today', { credentials: 'same-origin' });
      if (!response.ok) throw new Error(`Today API returned ${response.status}`);
      setData(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load Today');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function feedback(action: TodayAction, disposition: 'completed' | 'snoozed' | 'dismissed') {
    setWorking(action.source_key);
    setError(null);
    try {
      const response = await fetch('/api/v1/today/feedback', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_key: action.source_key,
          workstream: action.workstream,
          disposition,
          snoozed_until: disposition === 'snoozed' ? inSevenDays() : null,
        }),
      });
      if (!response.ok) throw new Error(`Could not ${disposition.replace('ed', '')} recommendation`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update recommendation');
    } finally {
      setWorking(null);
    }
  }

  return (
    <section className="today-command" aria-labelledby="today-title">
      <header className="today-command__header">
        <div>
          <div className="today-command__eyebrow"><span aria-hidden="true">✦</span> Explainable priority queue</div>
          <h2 id="today-title">Today’s five moves</h2>
          <p>One decision surface. Executive and Board records remain structurally separate.</p>
        </div>
        <button className="today-command__refresh" onClick={() => void load()} disabled={loading} aria-label="Refresh Today">
          <span aria-hidden="true" className={loading ? 'is-spinning' : ''}>↻</span> Refresh
        </button>
      </header>

      {data && (
        <div className="today-command__summary" aria-label="Recommendation summary">
          <div><strong>{data.available}</strong><span>eligible actions</span></div>
          <div><strong>{data.counts.executive}</strong><span>Executive</span></div>
          <div><strong>{data.counts.board}</strong><span>Board / NED</span></div>
          <div><strong>{data.actions.length}</strong><span>shown now</span></div>
        </div>
      )}

      {error && <div className="today-command__error" role="alert">{error}</div>}
      {loading && !data && <div className="today-command__empty">Ranking current actions…</div>}
      {!loading && data?.actions.length === 0 && (
        <div className="today-command__empty">
          <span className="today-command__empty-mark" aria-hidden="true">✓</span>
          <strong>Priority queue cleared.</strong>
          <span>There are no eligible actions in the next fourteen days.</span>
        </div>
      )}

      <div className="today-command__list">
        {data?.actions.map((action, index) => (
          <article className="today-action" key={action.source_key}>
            <div className="today-action__rank">{String(index + 1).padStart(2, '0')}</div>
            <div className="today-action__body">
              <div className="today-action__meta">
                <span className={`today-action__stream today-action__stream--${action.workstream}`}>
                  {action.workstream === 'executive' ? 'Executive' : 'Board / NED'}
                </span>
                <span>Score {action.score}</span>
                {action.due_date && <span>Due {new Date(`${action.due_date}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span>}
              </div>
              <a className="today-action__title" href={action.href}>{action.title}<span aria-hidden="true">›</span></a>
              {action.context && <p>{action.context}</p>}
              <ul className="today-action__reasons">
                {action.reasons.map(reason => <li key={reason}>{reason}</li>)}
              </ul>
            </div>
            <div className="today-action__controls" aria-label={`Actions for ${action.title}`}>
              {action.operations.includes('complete') && <button onClick={() => void feedback(action, 'completed')} disabled={working === action.source_key} title="Mark source task complete"><b aria-hidden="true">✓</b><span>Done</span></button>}
              {action.operations.includes('snooze') && <button onClick={() => void feedback(action, 'snoozed')} disabled={working === action.source_key} title="Snooze seven days"><b aria-hidden="true">◷</b><span>Snooze</span></button>}
              {action.operations.includes('dismiss') && <button onClick={() => void feedback(action, 'dismissed')} disabled={working === action.source_key} title="Dismiss generated suggestion"><b aria-hidden="true">×</b><span>Dismiss</span></button>}
            </div>
          </article>
        ))}
      </div>

      {data && <div className="today-overview">
        <section className="today-overview__panel" aria-labelledby="live-opportunities-title">
          <header><h3 id="live-opportunities-title">Live opportunities</h3><span>{data.overview.metrics.live_opportunities}</span></header>
          <div className="today-overview__rows">
            {data.overview.live_opportunities.length === 0 && <p className="today-overview__none">No live opportunities.</p>}
            {data.overview.live_opportunities.map(item => <a href={item.href} key={`${item.workstream}:${item.ulid}`} className="today-overview__row">
              <span className={`today-action__stream today-action__stream--${item.workstream}`}>{item.workstream === 'executive' ? 'Executive' : 'Board / NED'}</span>
              <strong>{item.organisation}</strong><span>{item.title} · {item.stage.replaceAll('_', ' ')}</span>
            </a>)}
          </div>
        </section>
        <section className="today-overview__panel" aria-labelledby="deadlines-title">
          <header><h3 id="deadlines-title">Deadlines</h3><span>{data.overview.metrics.overdue_actions} overdue</span></header>
          <div className="today-overview__rows">
            {data.overview.deadlines.length === 0 && <p className="today-overview__none">No dated actions in the next fortnight.</p>}
            {data.overview.deadlines.map(item => <a href={item.href} key={item.source_key} className="today-overview__row today-overview__row--deadline">
              <span className={`today-action__stream today-action__stream--${item.workstream}`}>{item.workstream === 'executive' ? 'Executive' : 'Board / NED'}</span>
              <strong>{new Date(`${item.due_date}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</strong><span>{item.title}</span>
            </a>)}
          </div>
        </section>
        <section className="today-overview__panel today-overview__panel--wide" aria-labelledby="cooling-title">
          <header><h3 id="cooling-title">Relationships cooling</h3><span>{data.overview.metrics.cooling_contacts} surfaced</span></header>
          <div className="today-overview__contacts">
            {data.overview.cooling_contacts.length === 0 && <p className="today-overview__none">Relationship coverage is current.</p>}
            {data.overview.cooling_contacts.map(item => <a href={item.href} key={`${item.workstream}:${item.ulid}`} className="today-overview__contact">
              <span className={`today-action__stream today-action__stream--${item.workstream}`}>{item.workstream === 'executive' ? 'Executive' : 'Board / NED'}</span>
              <strong>{item.name}</strong><span>{item.organisation || 'Independent contact'}</span><small>{item.last_contact_date ? `Last contact ${new Date(`${item.last_contact_date}T12:00:00`).toLocaleDateString('en-GB')}` : 'No contact recorded'}</small>
            </a>)}
          </div>
        </section>
      </div>}
    </section>
  );
}

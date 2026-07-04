import { useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost } from '../../lib/api';
import type {
  BoardInteraction,
  BoardTask,
  DueTouch,
  Engagement,
  EngagementCalendarRecord,
  Message,
} from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import Button from '../ui/Button';
import LogContactForm from '../partner/LogContactForm';
import { formatAbsoluteDate } from '../../lib/formatting';
import './NextActions.css';

function isOpen(e: Engagement): boolean {
  return e.stage !== 'closed' && !e.deleted_at;
}

/**
 * The single ranked "what should I do now" queue: overdue items first
 * (missed planned touches, lapsed cadence, past-due plan rows), then
 * messages awaiting approval, then everything due this week. Board items
 * surface as an aggregate count only — details stay in the board domain.
 */
export default function NextActions() {
  const pastDue = useFetch<EngagementCalendarRecord[]>(
    '/api/v1/engagement-calendar?due_window=past_due',
  );
  const thisWeek = useFetch<EngagementCalendarRecord[]>(
    '/api/v1/engagement-calendar?due_window=this_week',
  );
  const touches = useFetch<DueTouch[]>('/api/v1/planning/due-touches?window_days=7');
  const engagements = useFetch<Engagement[]>('/api/v1/engagements');
  const approvals = useFetch<Message[]>('/api/v1/messages?status=proposed');
  const boardTasks = useFetch<BoardTask[]>('/api/v1/board/tasks?status=open&due_within_days=14');
  const boardDue = useFetch<BoardInteraction[]>('/api/v1/board/interactions/due?within_days=14');

  const [busyUlid, setBusyUlid] = useState<string | null>(null);
  const [logTarget, setLogTarget] = useState<DueTouch | null>(null);

  const loading =
    pastDue.loading || thisWeek.loading || touches.loading ||
    engagements.loading || approvals.loading;

  async function complete(rec: EngagementCalendarRecord) {
    setBusyUlid(rec.ulid);
    try {
      await apiPost(`/api/v1/engagement-calendar/${rec.ulid}/complete`);
      await Promise.all([pastDue.refresh(), thisWeek.refresh()]);
    } finally {
      setBusyUlid(null);
    }
  }

  if (loading) return <section className="nextactions"><Skeleton width="100%" height={140} /></section>;

  const overdueRows = (pastDue.data ?? []).filter((r) => r.status !== 'complete');
  const weekRows = (thisWeek.data ?? []).filter((r) => r.status !== 'complete');
  const overdueTouches = (touches.data ?? []).filter((d) => d.status === 'overdue');
  const dueSoonTouches = (touches.data ?? []).filter((d) => d.status === 'due_soon');
  const neverContacted = (touches.data ?? []).filter((d) => d.status === 'no_planned_touch');
  const pendingApprovals = approvals.data ?? [];

  const horizon = new Date();
  horizon.setDate(horizon.getDate() + 7);
  const horizonIso = horizon.toISOString().slice(0, 10);
  const nextSteps = (engagements.data ?? []).filter(
    (e) => isOpen(e) && e.next_step && e.next_step_date && e.next_step_date <= horizonIso,
  );

  const boardCount = (boardTasks.data?.length ?? 0) + (boardDue.data?.length ?? 0);
  const empty =
    overdueRows.length === 0 && weekRows.length === 0 && overdueTouches.length === 0 &&
    dueSoonTouches.length === 0 && pendingApprovals.length === 0 && nextSteps.length === 0;

  return (
    <section className="nextactions" aria-labelledby="nextactions-h">
      <header className="nextactions__head">
        <h2 id="nextactions-h">Next actions</h2>
        <p className="nextactions__sub">Overdue first, then approvals, then this week</p>
      </header>

      {empty && (
        <p className="nextactions__empty">
          Nothing due. Start conversations from the <a href="/pipeline">pipeline</a> or plan ahead
          from the <a href="/engagement">calendar</a>.
        </p>
      )}

      {(overdueRows.length > 0 || overdueTouches.length > 0) && (
        <>
          <h3 className="nextactions__group nextactions__group--overdue">Overdue</h3>
          <ul className="nextactions__list">
            {overdueRows.map((r) => (
              <li className="nextactions__row" key={r.ulid}>
                <span className="nextactions__due is-overdue">{formatAbsoluteDate(r.due_date)}</span>
                <a className="nextactions__title" href="/engagement">{r.title}</a>
                <span className="nextactions__tag">plan</span>
                <Button variant="ghost" size="sm" onClick={() => complete(r)} disabled={busyUlid === r.ulid}>
                  Complete
                </Button>
              </li>
            ))}
            {overdueTouches.map((d) => (
              <li className="nextactions__row" key={d.partner_ulid}>
                <span className="nextactions__due is-overdue">
                  {d.days_until_next_touch != null && d.days_until_next_touch < 0
                    ? `${-d.days_until_next_touch}d late`
                    : `${d.days_since_last_contact ?? '?'}d silent`}
                </span>
                <a className="nextactions__title" href={`/partners/${d.partner_ulid}`}>
                  {d.partner_name} · {d.firm_name}
                </a>
                <span className="nextactions__tag">{d.due_source === 'cadence' ? 'cadence' : 'touch'}</span>
                <Button variant="ghost" size="sm" onClick={() => setLogTarget(d)}>Log contact</Button>
              </li>
            ))}
          </ul>
        </>
      )}

      {pendingApprovals.length > 0 && (
        <>
          <h3 className="nextactions__group">Awaiting your approval</h3>
          <ul className="nextactions__list">
            {pendingApprovals.slice(0, 5).map((m) => (
              <li className="nextactions__row" key={m.ulid}>
                <span className="nextactions__due">{m.kind ? m.kind.replace('_', ' ') : 'message'}</span>
                <a className="nextactions__title" href="/messages">
                  {m.subject || m.partner_name || m.recipient_hint || 'Proposed message'}
                </a>
                <span className="nextactions__tag">approve</span>
              </li>
            ))}
            {pendingApprovals.length > 5 && (
              <li className="nextactions__row">
                <a className="nextactions__title" href="/messages">
                  …and {pendingApprovals.length - 5} more in the approval inbox
                </a>
              </li>
            )}
          </ul>
        </>
      )}

      {(weekRows.length > 0 || dueSoonTouches.length > 0 || nextSteps.length > 0) && (
        <>
          <h3 className="nextactions__group">This week</h3>
          <ul className="nextactions__list">
            {weekRows.map((r) => (
              <li className="nextactions__row" key={r.ulid}>
                <span className="nextactions__due">{formatAbsoluteDate(r.due_date)}</span>
                <a className="nextactions__title" href="/engagement">{r.title}</a>
                <span className="nextactions__tag">plan</span>
                <Button variant="ghost" size="sm" onClick={() => complete(r)} disabled={busyUlid === r.ulid}>
                  Complete
                </Button>
              </li>
            ))}
            {dueSoonTouches.map((d) => (
              <li className="nextactions__row" key={d.partner_ulid}>
                <span className="nextactions__due">
                  {d.days_until_next_touch != null && d.days_until_next_touch <= 0
                    ? 'due now'
                    : `in ${d.days_until_next_touch}d`}
                </span>
                <a className="nextactions__title" href={`/partners/${d.partner_ulid}`}>
                  {d.partner_name} · {d.firm_name}
                  {d.next_touch_topic ? ` — ${d.next_touch_topic}` : ''}
                </a>
                <span className="nextactions__tag">{d.due_source === 'cadence' ? 'cadence' : 'touch'}</span>
                <Button variant="ghost" size="sm" onClick={() => setLogTarget(d)}>Log contact</Button>
              </li>
            ))}
            {nextSteps.map((e) => (
              <li className="nextactions__row" key={e.ulid}>
                <span className="nextactions__due">{formatAbsoluteDate(e.next_step_date!)}</span>
                <a className="nextactions__title" href={`/engagements/${e.ulid}`}>
                  {e.org_name ? `${e.org_name} — ` : ''}{e.role_title}: {e.next_step}
                </a>
                <span className="nextactions__tag">mandate</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="nextactions__quiet">
        {neverContacted.length > 0 && (
          <a href="/pipeline">{neverContacted.length} partners researched but never contacted →</a>
        )}
        {boardCount > 0 && (
          <a href="/board/outreach-due">{boardCount} board item{boardCount === 1 ? '' : 's'} due →</a>
        )}
      </div>

      {logTarget && (
        <LogContactForm
          open
          onClose={() => setLogTarget(null)}
          firmName={logTarget.firm_name}
          partnerName={logTarget.partner_name}
          onLogged={() => touches.refresh()}
        />
      )}
    </section>
  );
}

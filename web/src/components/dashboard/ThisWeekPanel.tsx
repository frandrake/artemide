import { useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost } from '../../lib/api';
import type { Engagement, EngagementCalendarRecord } from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import Button from '../ui/Button';
import { formatAbsoluteDate } from '../../lib/formatting';
import './ThisWeekPanel.css';

function isOpen(e: Engagement): boolean {
  return e.stage !== 'closed' && !e.deleted_at;
}

export default function ThisWeekPanel() {
  const pastDue = useFetch<EngagementCalendarRecord[]>(
    '/api/v1/engagement-calendar?due_window=past_due',
  );
  const thisWeek = useFetch<EngagementCalendarRecord[]>(
    '/api/v1/engagement-calendar?due_window=this_week',
  );
  const engagements = useFetch<Engagement[]>('/api/v1/engagements');
  const [busyUlid, setBusyUlid] = useState<string | null>(null);

  const loading = pastDue.loading || thisWeek.loading || engagements.loading;

  const rows: (EngagementCalendarRecord & { overdue: boolean })[] = [
    ...(pastDue.data ?? []).map((r) => ({ ...r, overdue: true })),
    ...(thisWeek.data ?? []).map((r) => ({ ...r, overdue: false })),
  ].filter((r) => r.status !== 'complete');

  const horizon = new Date();
  horizon.setDate(horizon.getDate() + 7);
  const horizonIso = horizon.toISOString().slice(0, 10);
  const nextSteps = (engagements.data ?? []).filter(
    (e) => isOpen(e) && e.next_step && e.next_step_date && e.next_step_date <= horizonIso,
  );

  async function complete(rec: EngagementCalendarRecord) {
    setBusyUlid(rec.ulid);
    try {
      await apiPost(`/api/v1/engagement-calendar/${rec.ulid}/complete`);
      await Promise.all([pastDue.refresh(), thisWeek.refresh()]);
    } finally {
      setBusyUlid(null);
    }
  }

  return (
    <section className="thisweek" aria-labelledby="thisweek-h">
      <header className="thisweek__head">
        <h2 id="thisweek-h">This week</h2>
        <p className="thisweek__sub">Plan rows due or overdue, and pipeline next steps</p>
      </header>

      {loading && <Skeleton width="100%" height={96} />}

      {!loading && rows.length === 0 && nextSteps.length === 0 && (
        <p className="thisweek__empty">Nothing due this week. Plan ahead from the calendar.</p>
      )}

      {!loading && rows.length > 0 && (
        <ul className="thisweek__list">
          {rows.map((r) => (
            <li className="thisweek__row" key={r.ulid}>
              <span
                className={`thisweek__due${r.overdue ? ' is-overdue' : ''}`}
              >{r.overdue ? `overdue · ${formatAbsoluteDate(r.due_date)}` : formatAbsoluteDate(r.due_date)}</span>
              <a className="thisweek__title" href="/engagement">{r.title}</a>
              {r.track && <span className="thisweek__track">{r.track.replace('-', ' ')}</span>}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => complete(r)}
                disabled={busyUlid === r.ulid}
              >Complete</Button>
            </li>
          ))}
        </ul>
      )}

      {!loading && nextSteps.length > 0 && (
        <>
          <h3 className="thisweek__subhead">Pipeline next steps</h3>
          <ul className="thisweek__list">
            {nextSteps.map((e) => (
              <li className="thisweek__row" key={e.ulid}>
                <span className="thisweek__due">{formatAbsoluteDate(e.next_step_date!)}</span>
                <a className="thisweek__title" href={`/engagements/${e.ulid}`}>
                  {e.org_name ? `${e.org_name} — ` : ''}{e.role_title}: {e.next_step}
                </a>
              </li>
            ))}
          </ul>
        </>
      )}

      <a className="thisweek__more" href="/engagement">View full calendar →</a>
    </section>
  );
}

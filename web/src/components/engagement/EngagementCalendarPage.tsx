import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPatch, apiPost, ApiError } from '../../lib/api';
import type { EngagementCalendarRecord, EngagementStatus } from '../../lib/types';
import Select from '../ui/Select';
import Button from '../ui/Button';
import Skeleton from '../ui/Skeleton';
import EmptyState from '../ui/EmptyState';
import Dialog from '../ui/Dialog';
import Input from '../ui/Input';
import { formatAbsoluteDate, formatRelativeDate } from '../../lib/formatting';
import './EngagementCalendarPage.css';

type DueWindow = 'all' | 'past_due' | 'this_week' | 'next_30' | 'next_90';

export default function EngagementCalendarPage() {
  const [status, setStatus] = useState<EngagementStatus | 'all'>('all');
  const [track, setTrack] = useState<string>('all');
  const [dueWindow, setDueWindow] = useState<DueWindow>('next_90');

  const path = useMemo(() => {
    const params = new URLSearchParams();
    if (status !== 'all') params.set('status', status);
    if (track !== 'all') params.set('track', track);
    if (dueWindow !== 'all') params.set('due_window', dueWindow);
    const q = params.toString();
    return q ? `/api/v1/engagement-calendar?${q}` : '/api/v1/engagement-calendar';
  }, [status, track, dueWindow]);

  const { data, loading, error, refresh } = useFetch<EngagementCalendarRecord[]>(path);

  const [rescheduling, setRescheduling] = useState<EngagementCalendarRecord | null>(null);
  const [newDate, setNewDate] = useState('');
  const [busyUlid, setBusyUlid] = useState<string | null>(null);

  // Group by track
  const grouped = useMemo(() => {
    const out: Record<string, EngagementCalendarRecord[]> = {};
    (data ?? []).forEach(r => {
      const t = r.track ?? '(no track)';
      if (!out[t]) out[t] = [];
      out[t].push(r);
    });
    return out;
  }, [data]);

  async function markComplete(rec: EngagementCalendarRecord) {
    setBusyUlid(rec.ulid);
    try {
      await apiPost(`/api/v1/engagement-calendar/${rec.ulid}/complete`);
      await refresh();
    } catch (e) { /* surface via reload */ }
    finally { setBusyUlid(null); }
  }

  async function confirmReschedule() {
    if (!rescheduling || !newDate) return;
    setBusyUlid(rescheduling.ulid);
    try {
      await apiPost(`/api/v1/engagement-calendar/${rescheduling.ulid}/reschedule`, { due_date: newDate });
      setRescheduling(null);
      setNewDate('');
      await refresh();
    } catch (e) { /* ignore */ }
    finally { setBusyUlid(null); }
  }

  return (
    <div className="engagement-page">
      <div className="engagement-page__filters">
        <Select
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.currentTarget.value as EngagementStatus | 'all')}
        >
          <option value="all">All statuses</option>
          <option value="not_set">Not set</option>
          <option value="planned">Planned</option>
          <option value="in_progress">In progress</option>
          <option value="complete">Complete</option>
        </Select>
        <Select
          label="Track"
          value={track}
          onChange={(e) => setTrack(e.currentTarget.value)}
        >
          <option value="all">All tracks</option>
          <option value="track-1">Track 1</option>
          <option value="track-2">Track 2</option>
          <option value="track-3">Track 3</option>
          <option value="track-4">Track 4</option>
          <option value="track-5">Track 5</option>
          <option value="track-6">Track 6</option>
        </Select>
        <Select
          label="Due window"
          value={dueWindow}
          onChange={(e) => setDueWindow(e.currentTarget.value as DueWindow)}
        >
          <option value="all">All</option>
          <option value="past_due">Past due</option>
          <option value="this_week">This week</option>
          <option value="next_30">Next 30 days</option>
          <option value="next_90">Next 90 days</option>
        </Select>
      </div>

      {loading && <Skeleton width="100%" height={120} />}
      {error && (
        <div className="engagement-page__error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={refresh}>Retry</button>
        </div>
      )}
      {data && data.length === 0 && (
        <EmptyState title="Nothing to do" description="No engagement entries match the current filters." />
      )}
      {data && data.length > 0 && (
        <div className="engagement-page__tracks">
          {Object.entries(grouped).map(([trackName, items]) => (
            <section key={trackName} className="engagement-track">
              <h2 className="engagement-track__heading">{trackName.replace('-', ' ')} · {items.length}</h2>
              <ul className="engagement-list">
                {items.map(item => (
                  <li key={item.ulid} className={`engagement-row engagement-row--${item.status}`}>
                    <div className="engagement-row__date">
                      <div className="engagement-row__date-abs">{formatAbsoluteDate(item.due_date)}</div>
                      <div className="engagement-row__date-rel">{formatRelativeDate(item.due_date)}</div>
                    </div>
                    <div className="engagement-row__main">
                      <div className="engagement-row__title">{item.title}</div>
                      {item.description && (
                        <div className="engagement-row__desc">{item.description}</div>
                      )}
                      <div className="engagement-row__meta">
                        <span className={`engagement-row__status engagement-row__status--${item.status}`}>
                          {item.status.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                    <div className="engagement-row__actions">
                      {item.status !== 'complete' && (
                        <Button
                          variant="secondary" size="sm"
                          onClick={() => markComplete(item)}
                          disabled={busyUlid === item.ulid}
                        >
                          Complete
                        </Button>
                      )}
                      <Button
                        variant="ghost" size="sm"
                        onClick={() => { setRescheduling(item); setNewDate(item.due_date); }}
                        disabled={busyUlid === item.ulid}
                      >
                        Reschedule
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      <Dialog
        open={!!rescheduling}
        onClose={() => setRescheduling(null)}
        title={`Reschedule: ${rescheduling?.title.slice(0, 60) ?? ''}`}
        children={
          <Input
            type="date"
            label="New due date"
            name="new_date"
            value={newDate}
            onChange={(e) => setNewDate(e.target.value)}
          />
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setRescheduling(null)}>Cancel</Button>
            <Button variant="primary" onClick={confirmReschedule} disabled={!newDate || busyUlid !== null}>
              Save
            </Button>
          </>
        }
      />
    </div>
  );
}

import { useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { DueTouch } from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import Button from '../ui/Button';
import LogContactForm from '../partner/LogContactForm';
import './UpcomingTouches.css';

export default function UpcomingTouches() {
  const { data, loading, error, refresh } = useFetch<DueTouch[]>(
    '/api/v1/planning/due-touches?window_days=14',
  );
  const [target, setTarget] = useState<DueTouch | null>(null);

  return (
    <section className="upcoming" aria-labelledby="upcoming-h">
      <header className="upcoming__head">
        <h2 id="upcoming-h">Upcoming touches</h2>
        <p className="upcoming__sub">Next two weeks</p>
      </header>

      {loading && (
        <div className="upcoming__list">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="upcoming__row upcoming__row--skeleton" key={i}>
              <Skeleton width="40%" height={16} />
              <Skeleton width="20%" height={14} />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="upcoming__error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={refresh}>Retry</button>
        </div>
      )}

      {data && data.length === 0 && (
        <p className="upcoming__empty">No partners due in the next two weeks.</p>
      )}

      {data && data.length > 0 && (
        <ul className="upcoming__list">
          {data.map((d) => {
            const overdue = d.status === 'overdue';
            const cadence = d.due_source === 'cadence' ? ' · cadence' : '';
            let indicator: string;
            if (d.status === 'overdue') {
              const late = d.days_until_next_touch != null && d.days_until_next_touch < 0
                ? -d.days_until_next_touch
                : d.days_since_last_contact;
              indicator = `${late ?? '?'} days overdue${cadence}`;
            } else if (d.status === 'due_soon') {
              indicator = d.days_until_next_touch != null && d.days_until_next_touch <= 0
                ? `due now${cadence}`
                : `in ${d.days_until_next_touch ?? '?'} days${cadence}`;
            } else {
              indicator = 'never contacted';
            }
            return (
              <li className="upcoming__row" key={d.partner_ulid}>
                <a className="upcoming__partner" href={`/partners/${d.partner_ulid}`}>
                  <span className="upcoming__name">{d.partner_name}</span>
                  <span className="upcoming__firm"> · {d.firm_name}</span>
                </a>
                <span
                  className={`upcoming__indicator${overdue ? ' is-overdue' : ''}`}
                >{indicator}</span>
                {d.next_touch_topic && (
                  <span className="upcoming__topic">{d.next_touch_topic}</span>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setTarget(d)}
                >Log contact</Button>
              </li>
            );
          })}
        </ul>
      )}

      <a className="upcoming__more" href="/plan">View full plan →</a>

      {target && (
        <LogContactForm
          open
          onClose={() => setTarget(null)}
          firmName={target.firm_name}
          partnerName={target.partner_name}
          onLogged={() => refresh()}
        />
      )}
    </section>
  );
}

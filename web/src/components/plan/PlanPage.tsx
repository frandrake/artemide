import { useMemo, useState } from 'react';
import { apiPost, ApiError } from '../../lib/api';
import { useFetch } from '../../lib/useFetch';
import type { CalendarStatus, QuarterPlan, ValueCalendar } from '../../lib/types';
import Button from '../ui/Button';
import Skeleton from '../ui/Skeleton';
import Select from '../ui/Select';
import LogContactForm from '../partner/LogContactForm';
import { formatAbsoluteDate } from '../../lib/formatting';
import './PlanPage.css';

function currentYearAndQuarter(): { year: number; quarter: number } {
  const now = new Date();
  return { year: now.getFullYear(), quarter: Math.floor(now.getMonth() / 3) + 1 };
}

export default function PlanPage() {
  const today = useMemo(currentYearAndQuarter, []);
  const [year, setYear] = useState(today.year);

  const yearList = [today.year - 1, today.year, today.year + 1];
  const quarters = [1, 2, 3, 4] as const;

  return (
    <div className="plan">
      <header className="plan__head">
        <h1>Quarterly value-exchange plan</h1>
        <div className="plan__year">
          <Select
            label="Year"
            value={String(year)}
            onChange={(e) => setYear(Number(e.currentTarget.value))}
          >
            {yearList.map((y) => <option key={y} value={y}>{y}</option>)}
          </Select>
        </div>
      </header>

      <div className="plan__grid">
        {quarters.map((q) => (
          <QuarterCard
            key={q}
            year={year}
            quarter={q}
            elevated={year === today.year && q === today.quarter}
          />
        ))}
      </div>
    </div>
  );
}

interface QuarterCardProps {
  year: number;
  quarter: number;
  elevated: boolean;
}

function QuarterCard({ year, quarter, elevated }: QuarterCardProps) {
  const plan = useFetch<QuarterPlan>(`/api/v1/planning/quarter?year=${year}&quarter=${quarter}`);
  const [logTarget, setLogTarget] = useState<{ firm: string; partner: string } | null>(null);

  return (
    <article className={`plan__card${elevated ? ' is-elevated' : ''}`}>
      <header className="plan__card-head">
        <h2 className="plan__card-title">Q{quarter} {year}</h2>
        {plan.data?.topic_status && <span className="plan__status">{plan.data.topic_status}</span>}
      </header>

      {plan.loading && <Skeleton width="80%" height={20} />}
      {plan.error && <p className="plan__error" role="alert">{plan.error}</p>}

      {plan.data && (
        <>
          <TopicEditor
            year={year}
            quarter={quarter}
            topic={plan.data.topic}
            onSaved={plan.refresh}
          />

          {elevated && (
            <>
              <hr className="plan__divider" />
              <section className="plan__suggested">
                <h3>Suggested contacts</h3>
                {plan.data.slots.length === 0 && (
                  <p className="plan__empty">No suggested slots yet — seed firms first.</p>
                )}
                <ol className="plan__slots">
                  {plan.data.slots.map((s) => (
                    <li key={`${s.firm_ulid}-${s.week_starting}`} className="plan__slot">
                      <div className="plan__slot-main">
                        <span className="plan__slot-week">Week of {formatAbsoluteDate(s.week_starting)}</span>
                        <span className="plan__slot-partner">
                          {s.partner_name ?? '—'}
                          <span className="plan__slot-firm"> · {s.firm_name}</span>
                        </span>
                        <span className="plan__slot-rationale">{s.rationale}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={!s.partner_name}
                        onClick={() =>
                          s.partner_name && setLogTarget({ firm: s.firm_name, partner: s.partner_name })
                        }
                      >Log contact</Button>
                    </li>
                  ))}
                </ol>
              </section>
              {plan.data.gaps.length > 0 && (
                <section className="plan__gaps">
                  <h3>Gaps</h3>
                  <ul>
                    {plan.data.gaps.map((g) => <li key={g}>{g}</li>)}
                  </ul>
                </section>
              )}
            </>
          )}
        </>
      )}

      {logTarget && (
        <LogContactForm
          open
          onClose={() => setLogTarget(null)}
          firmName={logTarget.firm}
          partnerName={logTarget.partner}
          onLogged={() => plan.refresh()}
        />
      )}
    </article>
  );
}

// ---------- inline topic edit ----------

interface TopicEditorProps {
  year: number;
  quarter: number;
  topic: string | null;
  onSaved: () => Promise<void>;
}

function TopicEditor({ year, quarter, topic, onSaved }: TopicEditorProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(topic ?? '');
  const [pending, setPending] = useState<string | null>(null); // optimistic value
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const next = draft.trim();
    if (!next) { setEditing(false); setError(null); return; }
    setSubmitting(true);
    setPending(next);
    setError(null);
    try {
      await apiPost<ValueCalendar>('/api/v1/planning/quarter-topic', {
        year, quarter, topic: next,
      });
      await onSaved();
      setEditing(false);
    } catch (e) {
      // Roll back the optimistic value on failure.
      setPending(null);
      setError(e instanceof ApiError ? e.message : 'Save failed.');
    } finally {
      setSubmitting(false);
    }
  }

  const display = pending ?? topic;

  if (editing) {
    return (
      <div className="plan__topic-edit">
        <input
          autoFocus
          value={draft}
          disabled={submitting}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); save(); }
            if (e.key === 'Escape') { setEditing(false); setDraft(topic ?? ''); setError(null); }
          }}
          placeholder="Value-exchange topic"
        />
        {error && <p className="plan__error" role="alert">{error}</p>}
      </div>
    );
  }

  if (display) {
    return (
      <p
        className={`plan__topic${pending ? ' is-pending' : ''}`}
        tabIndex={0}
        role="button"
        onClick={() => { setDraft(display); setEditing(true); }}
        onKeyDown={(e) => { if (e.key === 'Enter') { setDraft(display); setEditing(true); } }}
      >{display}</p>
    );
  }
  return (
    <Button variant="ghost" size="sm" onClick={() => { setDraft(''); setEditing(true); }}>
      Set topic
    </Button>
  );
}

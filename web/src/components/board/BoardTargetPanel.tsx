import { useState, type FormEvent } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPut } from '../../lib/api';
import type { BoardTargetStatus } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import './board.css';

const STAGE_LABELS: [keyof BoardTargetStatus['funnel'], string][] = [
  ['surfaced', 'Surfaced'],
  ['conflict_screen', 'Conflict screen'],
  ['chair_meeting', 'Chair meeting'],
  ['formal_process', 'Formal process'],
  ['final_nomco', 'Final nomco'],
  ['offer', 'Offer'],
  ['decision', 'Decision'],
];

export default function BoardTargetPanel() {
  const status = useFetch<BoardTargetStatus>('/api/v1/board/target/status');
  const [editing, setEditing] = useState(false);
  const [seats, setSeats] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status.loading) return <Skeleton height={96} />;
  if (status.error) return <p className="bd-error">{status.error}</p>;
  const s = status.data!;

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiPut('/api/v1/board/target', {
        seats_target: Number(seats || s.seats_target),
        target_date: targetDate || null,
      });
      setEditing(false);
      await status.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save target.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="bd-panel bd-target" aria-labelledby="bd-target-h">
      <div className="bd-target__head">
        <h2 id="bd-target-h">Target</h2>
        <span className={`bd-pill bd-rag bd-rag--${s.rag}`}>{s.rag.toUpperCase()}</span>
      </div>

      <p className="bd-target__headline">
        <strong>{s.seats_won}</strong> of <strong>{s.seats_target}</strong> seats won
        {s.target_date && (
          <span className="bd-card__sub">
            {' '}· target {s.target_date}
            {s.days_to_target != null && s.days_to_target >= 0 && ` (${s.days_to_target}d left)`}
            {s.days_to_target != null && s.days_to_target < 0 && ' (passed)'}
          </span>
        )}
        {!s.target_set && <span className="bd-card__sub"> · default goal — set your own</span>}
      </p>

      <div className="bd-target__funnel">
        {STAGE_LABELS.map(([key, label]) => (
          <span key={key} className="bd-target__stage" title={label}>
            <span className="bd-target__stage-count">{s.funnel[key] ?? 0}</span>
            <span className="bd-target__stage-label">{label}</span>
          </span>
        ))}
      </div>
      <p className="bd-card__sub">{s.open_opportunities} opportunit{s.open_opportunities === 1 ? 'y' : 'ies'} in motion</p>

      {!editing && (
        <button type="button" className="bd-btn bd-btn--ghost" onClick={() => {
          setSeats(String(s.seats_target));
          setTargetDate(s.target_date ?? '');
          setEditing(true);
        }}>{s.target_set ? 'Edit target' : 'Set target'}</button>
      )}

      {editing && (
        <form className="bd-target__form" onSubmit={save}>
          <label className="bd-field">
            <span>Seats</span>
            <input type="number" min={1} value={seats} onChange={(e) => setSeats(e.currentTarget.value)} required />
          </label>
          <label className="bd-field">
            <span>Target date</span>
            <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.currentTarget.value)} />
          </label>
          <button type="submit" className="bd-btn" disabled={saving}>Save</button>
          <button type="button" className="bd-btn bd-btn--ghost" onClick={() => setEditing(false)}>Cancel</button>
          {error && <p className="bd-error">{error}</p>}
        </form>
      )}
    </section>
  );
}

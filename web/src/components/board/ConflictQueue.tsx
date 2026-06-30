import { useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost } from '../../lib/api';
import type { BoardOpportunity, BoardConflictResult } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { titleCase } from './helpers';
import './board.css';

function ScreenForm({ o, onDone }: { o: BoardOpportunity; onDone: () => void }) {
  const [result, setResult] = useState<BoardConflictResult>('pass');
  const [isComp, setIsComp] = useState(false);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await apiPost(`/api/v1/board/opportunities/${o.ulid}/conflict-screen`, {
        opportunity_ulid: o.ulid, is_sp_competitor: isComp, result, notes: notes || null,
      });
      onDone();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bd-advance" style={{ flexWrap: 'wrap', gap: 8 }}>
      <label className="bd-field" style={{ marginBottom: 0 }}>
        <span>Result</span>
        <select value={result} onChange={(e) => setResult(e.target.value as BoardConflictResult)}>
          <option value="pass">pass (clears)</option>
          <option value="fail">fail (S&amp;P conflict)</option>
          <option value="pending">pending</option>
        </select>
      </label>
      <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 'var(--text-sm)' }}>
        <input type="checkbox" checked={isComp} onChange={(e) => setIsComp(e.target.checked)} />
        S&amp;P competitor
      </label>
      <input style={{ padding: '8px 10px', fontSize: 'var(--text-sm)', border: '1px solid var(--light-gray)', borderRadius: 'var(--radius-sm)' }}
        placeholder="notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <button className="bd-btn" disabled={busy} onClick={submit}>Record screen</button>
    </div>
  );
}

export default function ConflictQueue() {
  const { data, loading, error, refresh } = useFetch<BoardOpportunity[]>(
    '/api/v1/board/opportunities?conflict_cleared=pending');

  if (loading) return <Skeleton height={240} />;
  if (error) return <p className="bd-error">{error}</p>;
  if (!data || data.length === 0) {
    return <EmptyState title="Conflict-screen queue is clear." description="No opportunities awaiting a conflict screen." />;
  }

  return (
    <div className="bd-detail">
      {data.map((o) => (
        <div className="bd-panel" key={o.ulid}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <a className="bd-kcard__org" href={`/board/opportunities/${o.ulid}`}>{o.organisation}</a>
            <span className="bd-col__count">{titleCase(o.stage)}</span>
          </div>
          {o.source_text && <div className="bd-card__sub">Source: {o.source_text}</div>}
          <ScreenForm o={o} onDone={refresh} />
        </div>
      ))}
    </div>
  );
}

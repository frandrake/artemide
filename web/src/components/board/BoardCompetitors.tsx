import { useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost } from '../../lib/api';
import type { BoardCompetitor } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import './board.css';

export default function BoardCompetitors() {
  const { data, loading, error, refresh } = useFetch<BoardCompetitor[]>('/api/v1/board/competitors');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await apiPost('/api/v1/board/competitors', { name: name.trim() });
      setName('');
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Skeleton height={240} />;
  if (error) return <p className="bd-error">{error}</p>;

  return (
    <div>
      <p className="bd-subhead" style={{ marginBottom: 'var(--space-2)' }}>
        S&amp;P competitors the conflict screen checks against (editable as new names surface).
      </p>
      <div className="bd-advance" style={{ marginBottom: 'var(--space-3)' }}>
        <input style={{ padding: '8px 10px', border: '1px solid var(--light-gray)', borderRadius: 'var(--radius-sm)' }}
          placeholder="Add competitor name" value={name}
          onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && add()} />
        <button className="bd-btn" disabled={busy} onClick={add}>Add</button>
      </div>
      <table className="bd-table">
        <thead><tr><th>Name</th><th>Active</th><th>Notes</th></tr></thead>
        <tbody>
          {(data ?? []).map((c) => (
            <tr key={c.ulid}><td>{c.name}</td><td>{c.active ? 'yes' : 'no'}</td><td>{c.notes ?? '—'}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

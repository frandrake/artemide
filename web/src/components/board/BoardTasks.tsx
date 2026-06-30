import { useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost } from '../../lib/api';
import type { BoardTask } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import './board.css';

export default function BoardTasks() {
  const { data, loading, error, refresh } = useFetch<BoardTask[]>('/api/v1/board/tasks');
  const [title, setTitle] = useState('');
  const [due, setDue] = useState('');
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await apiPost('/api/v1/board/tasks', { title: title.trim(), due_date: due || null });
      setTitle(''); setDue('');
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function done(t: BoardTask) {
    await apiPost(`/api/v1/board/tasks/${t.ulid}/done`);
    await refresh();
  }

  if (loading) return <Skeleton height={240} />;
  if (error) return <p className="bd-error">{error}</p>;

  return (
    <div>
      <div className="bd-advance" style={{ marginBottom: 'var(--space-3)', flexWrap: 'wrap' }}>
        <input style={{ padding: '8px 10px', border: '1px solid var(--light-gray)', borderRadius: 'var(--radius-sm)' }}
          placeholder="Task title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input type="date" style={{ padding: '8px 10px', border: '1px solid var(--light-gray)', borderRadius: 'var(--radius-sm)' }}
          value={due} onChange={(e) => setDue(e.target.value)} />
        <button className="bd-btn" disabled={busy} onClick={add}>Add task</button>
      </div>
      <table className="bd-table">
        <thead><tr><th>Status</th><th>Title</th><th>Due</th><th></th></tr></thead>
        <tbody>
          {(data ?? []).map((t) => (
            <tr key={t.ulid}>
              <td><span className={`bd-pill ${t.status === 'done' ? 'bd-pill--warm' : ''}`}>{t.status}</span></td>
              <td>{t.title}</td>
              <td>{t.due_date ?? '—'}</td>
              <td>{t.status === 'open' && <button className="bd-btn bd-btn--ghost" onClick={() => done(t)}>Done</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

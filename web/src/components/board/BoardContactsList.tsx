import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { BoardContact } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { titleCase } from './helpers';
import './board.css';

export default function BoardContactsList() {
  const [stale, setStale] = useState(false);
  const path = useMemo(() => `/api/v1/board/contacts${stale ? '?stale=true' : ''}`, [stale]);
  const { data, loading, error } = useFetch<BoardContact[]>(path);

  if (loading) return <Skeleton height={280} />;
  if (error) return <p className="bd-error">{error}</p>;
  if (!data || data.length === 0) {
    return <EmptyState title="No board contacts yet." description="Add chairs, partners and connectors." />;
  }

  return (
    <div>
      <div className="bd-filters">
        <label className="bd-filter" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={stale} onChange={(e) => setStale(e.target.checked)} />
          <span>Show only contacts to re-verify (&gt;90 days)</span>
        </label>
      </div>
      <table className="bd-table">
        <thead>
          <tr><th>Name</th><th>Role</th><th>Firm</th><th>Relationship</th><th>Last contact</th><th></th></tr>
        </thead>
        <tbody>
          {data.map((c) => (
            <tr key={c.ulid}>
              <td>{c.name}</td>
              <td>{c.role_title ?? '—'}</td>
              <td>{c.firm_name ?? '—'}</td>
              <td><span className={`bd-pill bd-pill--${c.relationship}`}>{c.relationship}</span></td>
              <td>{c.last_contact_date ?? '—'}</td>
              <td>{c.verify_before_send && <span className="bd-pill bd-pill--flag">verify before send</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

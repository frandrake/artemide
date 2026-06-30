import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { BoardFirm, BoardFirmStatus } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { titleCase } from './helpers';
import './board.css';

const STATUSES: BoardFirmStatus[] = [
  'to_approach', 'to_register', 'to_join', 'queued', 'contacted', 'in_dialogue', 'dormant',
  'drafted', 'consider', 'monitor',
];

export default function BoardFirmsList() {
  const [status, setStatus] = useState<string>('');
  const path = useMemo(() => {
    const p = new URLSearchParams();
    if (status) p.set('status', status);
    return `/api/v1/board/firms?${p.toString()}`;
  }, [status]);
  const { data, loading, error } = useFetch<BoardFirm[]>(path);

  const byTier = useMemo(() => {
    const groups: Record<string, BoardFirm[]> = {};
    for (const f of data ?? []) {
      const key = f.tier != null ? `Tier ${f.tier}` : 'Untiered';
      (groups[key] ??= []).push(f);
    }
    return groups;
  }, [data]);

  if (loading) return <Skeleton height={320} />;
  if (error) return <p className="bd-error">{error}</p>;
  if (!data || data.length === 0) {
    return <EmptyState title="No board firms yet." description="Add one, or import the tiered ledger via /board/import." />;
  }

  return (
    <div>
      <div className="bd-filters">
        <div className="bd-filter">
          <label htmlFor="bf-status">Status</label>
          <select id="bf-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            {STATUSES.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </select>
        </div>
      </div>
      {Object.keys(byTier).sort().map((tier) => (
        <section className="bd-tier" key={tier}>
          <h2 className="bd-tier__label">{tier} <span className="bd-col__count">({byTier[tier].length})</span></h2>
          <div className="bd-cards">
            {byTier[tier].map((f) => (
              <a className="bd-card" href={`/board/firms/${f.ulid}`} key={f.ulid}>
                <div className="bd-card__name">{f.name}</div>
                <div className="bd-card__sub">
                  {f.firm_type ? titleCase(f.firm_type) : '—'}
                  {f.geography.length > 0 ? ` · ${f.geography.join(', ')}` : ''}
                </div>
                <div className="bd-card__meta">
                  <span className="bd-pill">{titleCase(f.status)}</span>
                  {f.ai_on_boards_hook && <span className="bd-pill">AI hook</span>}
                </div>
                {f.next_action && <div className="bd-card__sub">Next: {f.next_action}</div>}
              </a>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

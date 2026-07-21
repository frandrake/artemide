import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { BoardOpportunity, BoardOppInterest } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { titleCase, verdictTone } from './helpers';
import './board.css';

const INTERESTS: BoardOppInterest[] = ['preferred', 'active', 'exploratory', 'pass'];

export default function BoardOpportunitiesLog() {
  const [interest, setInterest] = useState<string>('');
  const path = useMemo(() => {
    const p = new URLSearchParams({ sort: 'date_surfaced' });
    if (interest) p.set('interest', interest);
    return `/api/v1/board/opportunities?${p.toString()}`;
  }, [interest]);
  const { data, loading, error } = useFetch<BoardOpportunity[]>(path);

  if (loading) return <Skeleton height={280} />;
  if (error) return <p className="bd-error">{error}</p>;
  if (!data || data.length === 0) {
    return <EmptyState title="No board opportunities yet." description="Surface a seat to begin tracking it." />;
  }

  return (
    <div>
      <div className="bd-filters">
        <div className="bd-filter">
          <label htmlFor="bo-int">Interest</label>
          <select id="bo-int" value={interest} onChange={(e) => setInterest(e.target.value)}>
            <option value="">All</option>
            {INTERESTS.map((i) => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
      </div>
      <table className="bd-table">
        <thead>
          <tr>
            <th>Organisation</th><th>Appointment</th><th>Board type</th><th>Surfaced</th>
            <th>Stage</th><th>Conflict</th><th>Interest</th><th>Board seat evaluation</th>
          </tr>
        </thead>
        <tbody>
          {data.map((o) => (
            <tr key={o.ulid}>
              <td><a href={`/board/opportunities/${o.ulid}`}>{o.organisation}</a></td>
              <td>{o.appointment_category ? titleCase(o.appointment_category) : (o.role ? o.role.toUpperCase() : 'Unclassified')}</td>
              <td>{o.board_type ? titleCase(o.board_type) : '—'}</td>
              <td>{o.date_surfaced ?? '—'}</td>
              <td>{titleCase(o.stage)}</td>
              <td>
                <span className={`bd-pill ${o.conflict_cleared === 'yes' ? 'bd-pill--warm' : o.conflict_cleared === 'no' ? 'bd-pill--flag' : ''}`}>
                  {o.conflict_cleared}
                </span>
              </td>
              <td>{o.interest}</td>
              <td>{o.eval_verdict ? <><span className={`bd-pill ${verdictTone(o.eval_verdict)}`}>{titleCase(o.eval_verdict)}</span>{o.eval_weighted_total != null && ` ${o.eval_weighted_total.toFixed(2)} / 5`}</> : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

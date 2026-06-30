import { useMemo } from 'react';
import { useFetch } from '../../lib/useFetch';
import { BOARD_EVAL_DIMENSIONS } from '../../lib/types';
import type { BoardOpportunity, BoardEvaluationCompare } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { titleCase, verdictTone } from './helpers';
import './board.css';

export default function EvaluationCompare() {
  // Compare every live opportunity that carries a weighted total.
  const { data: opps, loading, error } = useFetch<BoardOpportunity[]>(
    '/api/v1/board/opportunities?sort=eval');

  const ulids = useMemo(
    () => (opps ?? []).filter((o) => o.eval_weighted_total != null).map((o) => o.ulid),
    [opps]);
  const query = ulids.map((u) => `ulid=${u}`).join('&');
  const { data: cmp } = useFetch<BoardEvaluationCompare>(
    ulids.length ? `/api/v1/board/opportunities/evaluations/compare?${query}` : null, [query]);

  if (loading) return <Skeleton height={240} />;
  if (error) return <p className="bd-error">{error}</p>;
  if (!ulids.length) {
    return <EmptyState title="No scored opportunities yet." description="Evaluate two or more opportunities to compare them." />;
  }
  if (!cmp) return <Skeleton height={240} />;

  return (
    <table className="bd-table">
      <thead>
        <tr>
          <th>Dimension</th>
          {cmp.opportunities.map((o) => <th key={o.opportunity_ulid}>{o.organisation}</th>)}
        </tr>
      </thead>
      <tbody>
        {BOARD_EVAL_DIMENSIONS.map((d) => (
          <tr key={d.key}>
            <td>{d.label} <span className="bd-eval-row__weight">×{d.weight}%</span></td>
            {cmp.opportunities.map((o) => (
              <td key={o.opportunity_ulid}>{o.scores ? (o.scores[d.key] ?? '—') : '—'}</td>
            ))}
          </tr>
        ))}
        <tr>
          <td><strong>Weighted total</strong></td>
          {cmp.opportunities.map((o) => (
            <td key={o.opportunity_ulid}><strong>{o.weighted_total?.toFixed(2) ?? '—'}</strong></td>
          ))}
        </tr>
        <tr>
          <td><strong>Verdict</strong></td>
          {cmp.opportunities.map((o) => (
            <td key={o.opportunity_ulid}>
              {o.verdict ? <span className={`bd-pill ${verdictTone(o.verdict)}`}>{titleCase(o.verdict)}</span> : '—'}
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  );
}

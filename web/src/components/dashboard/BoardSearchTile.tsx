import { useFetch } from '../../lib/useFetch';
import type { BoardFirm, BoardOpportunity } from '../../lib/types';
import './BoardSearchTile.css';

/**
 * Quiet entry point to the confidential board/NED domain from the exec
 * dashboard. Shows aggregate counts only (no individual board records) — a
 * deliberate, minimal exception to keeping the board domain off exec views.
 */
export default function BoardSearchTile() {
  const firms = useFetch<BoardFirm[]>('/api/v1/board/firms');
  const opps = useFetch<BoardOpportunity[]>('/api/v1/board/opportunities');

  const firmCount = firms.data?.length;
  const oppCount = opps.data?.length;
  const seats = oppCount === 1 ? 'seat' : 'seats';

  return (
    <a className="board-tile" href="/board" aria-label="Open the board search domain">
      <div className="board-tile__main">
        <span className="board-tile__chip">BOARD</span>
        <span className="board-tile__title">Board search</span>
        <span className="board-tile__counts">
          {firmCount ?? '—'} firms · {oppCount ?? '—'} live {seats}
        </span>
      </div>
      <span className="board-tile__cta">Open Board →</span>
    </a>
  );
}

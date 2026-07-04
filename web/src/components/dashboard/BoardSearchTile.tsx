import { useFetch } from '../../lib/useFetch';
import type { BoardFirm, BoardTargetStatus } from '../../lib/types';
import './BoardSearchTile.css';

/**
 * Quiet entry point to the confidential board/NED domain from the exec
 * dashboard. Shows aggregate counts only (no individual board records) — a
 * deliberate, minimal exception to keeping the board domain off exec views.
 */
export default function BoardSearchTile() {
  const firms = useFetch<BoardFirm[]>('/api/v1/board/firms');
  const target = useFetch<BoardTargetStatus>('/api/v1/board/target/status');

  const firmCount = firms.data?.length;
  const t = target.data;

  return (
    <a className="board-tile" href="/board" aria-label="Open the board search domain">
      <div className="board-tile__main">
        <span className="board-tile__chip">BOARD</span>
        <span className="board-tile__title">Board search</span>
        <span className="board-tile__counts">
          {t
            ? `${t.seats_won}/${t.seats_target} seats · ${t.open_opportunities} in motion · ${firmCount ?? '—'} firms`
            : `${firmCount ?? '—'} firms`}
        </span>
        {t && <span className={`board-tile__rag board-tile__rag--${t.rag}`} title={`Board search ${t.rag}`} />}
      </div>
      <span className="board-tile__cta">Open Board →</span>
    </a>
  );
}

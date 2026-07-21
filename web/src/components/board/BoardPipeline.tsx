import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost } from '../../lib/api';
import { BOARD_STAGE_ORDER } from '../../lib/types';
import type { BoardOpportunity, BoardStage } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { titleCase, verdictTone } from './helpers';
import './board.css';

export default function BoardPipeline() {
  const { data, loading, error, refresh } = useFetch<BoardOpportunity[]>('/api/v1/board/opportunities');
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const byStage = useMemo(() => {
    const groups: Record<string, BoardOpportunity[]> = {};
    for (const s of BOARD_STAGE_ORDER) groups[s] = [];
    for (const o of data ?? []) (groups[o.stage] ??= []).push(o);
    return groups;
  }, [data]);

  async function advance(o: BoardOpportunity) {
    const idx = BOARD_STAGE_ORDER.indexOf(o.stage);
    const next = BOARD_STAGE_ORDER[idx + 1];
    if (!next) return;
    setBusy(o.ulid);
    setToast(null);
    try {
      const updated = await apiPost<BoardOpportunity>(
        `/api/v1/board/opportunities/${o.ulid}/advance`, { to_stage: next });
      if (updated.warnings && updated.warnings.length > 0) {
        setToast(`${o.organisation}: ${updated.warnings.join(' ')}`);
      }
      await refresh();
    } catch (e) {
      setToast(e instanceof Error ? e.message : 'advance failed');
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Skeleton height={320} />;
  if (error) return <p className="bd-error">{error}</p>;
  if (!data || data.length === 0) {
    return <EmptyState title="No board opportunities in the pipeline." description="Surface a seat to begin." />;
  }

  return (
    <div>
      {toast && <div className="bd-toast" role="status">⚑ {toast}</div>}
      <div className="bd-board">
        {BOARD_STAGE_ORDER.map((stage: BoardStage) => (
          <div className="bd-col" key={stage}>
            <div className="bd-col__head">
              <span className="bd-col__name">{titleCase(stage)}</span>
              <span className="bd-col__count">{byStage[stage].length}</span>
            </div>
            {byStage[stage].map((o) => (
              <div className="bd-kcard" key={o.ulid}>
                <a className="bd-kcard__org" href={`/board/opportunities/${o.ulid}`}>{o.organisation}</a>
                <div className="bd-kcard__meta">
                  {o.role && <span className="bd-pill">{o.role.toUpperCase()}</span>}
                  <span className={`bd-pill ${o.conflict_cleared === 'yes' ? 'bd-pill--warm' : o.conflict_cleared === 'no' ? 'bd-pill--flag' : ''}`}>
                    {o.conflict_cleared}
                  </span>
                  {o.appointment_category && <span className="bd-pill">{titleCase(o.appointment_category)}</span>}
                  {o.eval_weighted_total != null && <span className="bd-pill">{o.eval_weighted_total.toFixed(2)} / 5</span>}
                  {o.eval_verdict && <span className={`bd-pill ${verdictTone(o.eval_verdict)}`}>{o.eval_verdict}</span>}
                </div>
                {BOARD_STAGE_ORDER.indexOf(o.stage) < BOARD_STAGE_ORDER.length - 1 && (
                  <div className="bd-advance">
                    <button className="bd-btn bd-btn--ghost" disabled={busy === o.ulid} onClick={() => advance(o)}>
                      Advance →
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

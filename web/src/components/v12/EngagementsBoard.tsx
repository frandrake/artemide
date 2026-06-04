import { useMemo, useState } from 'react';
import clsx from 'clsx';
import { useFetch } from '../../lib/useFetch';
import type { Engagement, EngagementInterest, ScaleBand } from '../../lib/types';
import { STAGE_ORDER } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { Badge } from '../ui/Badge';
import { fitTone, titleCase } from './helpers';
import './v12.css';

const INTERESTS: EngagementInterest[] = ['preferred', 'active', 'exploratory', 'pass'];
const BANDS: ScaleBand[] = ['fortune_500', 'global_equivalent', 'pe_backed', 'other'];

function FitBadge({ e }: { e: Engagement }) {
  const tone = fitTone(e);
  const label = tone === 'fail' ? '⚑ ' + (e.fit_score ?? '—') : (e.fit_score ?? '—');
  return <span className={clsx('fit', `fit--${tone}`)}>fit {label}</span>;
}

export default function EngagementsBoard() {
  const { data, loading, error } = useFetch<Engagement[]>('/api/v1/engagements?sort=fit');
  const [interest, setInterest] = useState<string>('');
  const [band, setBand] = useState<string>('');

  const byStage = useMemo(() => {
    const groups: Record<string, Engagement[]> = {};
    for (const s of STAGE_ORDER) groups[s] = [];
    for (const e of data ?? []) {
      if (e.stage === 'closed') continue;
      if (interest && e.interest !== interest) continue;
      if (band && e.org_scale_band !== band) continue;
      (groups[e.stage] ??= []).push(e);
    }
    return groups;
  }, [data, interest, band]);

  if (loading) return <Skeleton height={320} />;
  if (error) return <p className="v12-error">{error}</p>;
  const all = data ?? [];
  if (all.length === 0) {
    return <EmptyState title="No engagements yet." description="Surface one via the API, MCP, or Radar." />;
  }

  return (
    <div>
      <div className="v12-filters">
        <div className="v12-filter">
          <label htmlFor="f-int">Interest</label>
          <select id="f-int" value={interest} onChange={(ev) => setInterest(ev.target.value)}>
            <option value="">All</option>
            {INTERESTS.map((i) => <option key={i} value={i}>{i}</option>)}
          </select>
        </div>
        <div className="v12-filter">
          <label htmlFor="f-band">Scale band</label>
          <select id="f-band" value={band} onChange={(ev) => setBand(ev.target.value)}>
            <option value="">All</option>
            {BANDS.map((b) => <option key={b} value={b}>{titleCase(b)}</option>)}
          </select>
        </div>
      </div>
      <div className="board">
        {STAGE_ORDER.map((stage) => (
          <div className="board-col" key={stage}>
            <h3>{titleCase(stage)} <span className="count">{byStage[stage].length}</span></h3>
            {byStage[stage].map((e) => (
              <a className="eng-card" href={`/engagements/${e.ulid}`} key={e.ulid}>
                <div className="org">{e.org_name ?? '—'}</div>
                <div className="role">{e.role_title}</div>
                <div className="meta">
                  <FitBadge e={e} />
                  <Badge tone={e.interest === 'preferred' ? 'accent' : 'info'}>{e.interest}</Badge>
                </div>
                {e.next_step && <div className="rationale">{e.next_step}{e.next_step_date ? ` · ${e.next_step_date}` : ''}</div>}
              </a>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

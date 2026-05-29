import { useFetch } from '../../lib/useFetch';
import clsx from 'clsx';
import type { Engagement, Message, ProgrammeStatus } from '../../lib/types';
import { STAGE_ORDER } from '../../lib/types';
import { ragClass, titleCase } from './helpers';
import './v12.css';

/** Dashboard additions: a slim programme banner + pipeline-by-stage + awaiting-approval. */
export default function ProgrammeBanner() {
  const status = useFetch<ProgrammeStatus>('/api/v1/programme/status');
  const engagements = useFetch<Engagement[]>('/api/v1/engagements?sort=fit');
  const proposed = useFetch<Message[]>('/api/v1/messages?status=proposed');

  const s = status.data;
  const counts: Record<string, number> = {};
  for (const st of STAGE_ORDER) counts[st] = 0;
  for (const e of engagements.data ?? []) if (e.stage in counts) counts[e.stage] += 1;
  const awaiting = (proposed.data ?? []).length;

  return (
    <div>
      {s && (
        <div className="prog-banner">
          <span><span className={clsx('rag-dot', ragClass(s.overall_rag))} /><strong>{s.overall_rag.toUpperCase()}</strong></span>
          <span><strong>{s.days_to_target}</strong> days to {s.target_date}</span>
          <span className="slip">
            {s.target_at_risk ? '⚑ target at risk — ' : ''}
            {s.phases.map((p) => `${titleCase(p.phase)} ${p.rag}`).join(' · ')}
          </span>
        </div>
      )}
      <div className="v12-grid-2" style={{ marginBottom: 'var(--space-3)' }}>
        <div className="card card--padded card--bordered">
          <h3 className="panel-title">Pipeline by stage</h3>
          <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
            {STAGE_ORDER.map((st) => (
              <a key={st} href={`/engagements`} style={{ textDecoration: 'none', color: 'inherit' }}>
                <span style={{ textTransform: 'capitalize', color: 'var(--charcoal-muted)' }}>{st}</span>{' '}
                <strong>{counts[st]}</strong>
              </a>
            ))}
          </div>
        </div>
        <a href="/messages" style={{ textDecoration: 'none', color: 'inherit' }}>
          <div className={clsx('card', 'card--padded', 'card--bordered', awaiting > 0 && 'awaiting-zero')}>
            <h3 className="panel-title">Awaiting approval</h3>
            <div className="days-figure" style={{ fontSize: 36 }}>{awaiting}</div>
            <div className="rationale">proposed message{awaiting === 1 ? '' : 's'}</div>
          </div>
        </a>
      </div>
    </div>
  );
}

import { useFetch } from '../../lib/useFetch';
import type { Milestone, ProgrammeStatus } from '../../lib/types';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Skeleton } from '../ui/Skeleton';
import { ragClass, titleCase } from './helpers';
import './v12.css';

const PHASES = ['build', 'seed', 'run', 'close', 'exit'];

export default function ProgrammePage() {
  const status = useFetch<ProgrammeStatus>('/api/v1/programme/status');
  const milestones = useFetch<Milestone[]>('/api/v1/programme/milestones');

  if (status.loading || milestones.loading) return <Skeleton height={280} />;
  if (status.error) return <p className="v12-error">{status.error}</p>;
  const s = status.data;
  const ms = milestones.data ?? [];
  if (!s) return null;

  const phaseRag = (p: string) => s.phases.find((x) => x.phase === p);
  const phaseMilestone = (p: string) => ms.find((m) => m.phase === p);

  return (
    <div>
      <Card style={{ marginBottom: 'var(--space-3)', display: 'flex', gap: 'var(--space-4)', alignItems: 'center' }}>
        <div>
          <div className="days-figure">{s.days_to_target}</div>
          <div className="rationale">days to {s.target_date}</div>
        </div>
        <div>
          <div><span className={`rag-dot ${ragClass(s.overall_rag)}`} />Overall: <strong>{s.overall_rag}</strong></div>
          {s.target_at_risk && <Badge tone="accent">target at risk</Badge>}
        </div>
      </Card>

      <div className="phase-track">
        {PHASES.map((p) => {
          const r = phaseRag(p);
          const m = phaseMilestone(p);
          return (
            <div className="phase-card" key={p}>
              <h3 style={{ textTransform: 'capitalize', margin: '0 0 6px' }}>
                <span className={`rag-dot ${ragClass(r?.rag ?? 'amber')}`} />{p}
              </h3>
              {m && <div className="rationale">{m.label}</div>}
              {m && <div className="when">{m.target_date} · {m.status}</div>}
              {r && <p style={{ fontSize: 'var(--text-sm)', marginTop: 6 }}>{r.detail}</p>}
            </div>
          );
        })}
      </div>

      <Card>
        <h2 className="panel-title">Slippage read-out</h2>
        <ul>
          {s.phases.map((p) => (
            <li key={p.phase}>
              <span className={`rag-dot ${ragClass(p.rag)}`} />
              <strong style={{ textTransform: 'capitalize' }}>{titleCase(p.phase)}</strong>: {p.detail}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

import { useEffect, useState } from 'react';
import clsx from 'clsx';
import { apiGet, apiPost, ApiError } from '../../lib/api';
import type { Engagement } from '../../lib/types';
import { STAGE_ORDER } from '../../lib/types';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Skeleton } from '../ui/Skeleton';
import { fitTone, gbp, titleCase, ulidFromPath } from './helpers';
import './v12.css';

function nextStages(stage: string): string[] {
  if (stage === 'closed') return [];
  const idx = STAGE_ORDER.indexOf(stage as never);
  const forward = idx >= 0 ? STAGE_ORDER.slice(idx + 1) : [];
  return [...forward, 'closed'];
}

function FitBreakdown({ e }: { e: Engagement }) {
  const bd = e.fit_breakdown;
  if (!bd || typeof bd !== 'object') return <p className="rationale">Not yet scored.</p>;
  const obj = bd as Record<string, unknown>;
  const dims = (obj.dimensions ?? {}) as Record<string, { raw: number; weight: number }>;
  return (
    <div>
      {obj.hard_fail ? <Badge tone="accent">hard filter failed: {(obj.failed_filters as string[] ?? []).join(', ')}</Badge> : null}
      {Object.entries(dims).map(([dim, d]) => (
        <div className="bar-row" key={dim}>
          <span>{titleCase(dim)}</span>
          <span className="bar-track"><span className="bar-fill" style={{ width: `${d.raw}%` }} /></span>
          <span>{d.raw}</span>
        </div>
      ))}
    </div>
  );
}

export default function EngagementDetail() {
  const ulid = ulidFromPath('engagements');
  const [e, setE] = useState<Engagement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!ulid) { setError('Invalid URL'); setLoading(false); return; }
    setLoading(true);
    try {
      setE(await apiGet<Engagement>(`/api/v1/engagements/${ulid}`));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load.');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  async function advance(to: string) {
    if (!ulid) return;
    setBusy(true);
    try {
      await apiPost(`/api/v1/engagements/${ulid}/advance`, { to_stage: to });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Advance failed.');
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Skeleton height={320} />;
  if (error) return <p className="v12-error">{error}</p>;
  if (!e) return null;

  return (
    <div>
      <div className="detail-header">
        <h1>{e.org_name}</h1>
        <Badge tone="info">{e.role_title}</Badge>
        <Badge tone="neutral">{e.stage}</Badge>
        <Badge tone={e.interest === 'preferred' ? 'accent' : 'info'}>{e.interest}</Badge>
        <span className={clsx('fit', `fit--${fitTone(e)}`)}>fit {e.fit_score ?? '—'}</span>
      </div>

      <div className="v12-filters">
        {nextStages(e.stage).map((s) => (
          <Button key={s} variant={s === 'closed' ? 'ghost' : 'secondary'} size="sm"
                  loading={busy} onClick={() => advance(s)}>
            → {titleCase(s)}
          </Button>
        ))}
      </div>

      <div className="v12-grid">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <Card>
            <h2 className="panel-title">Compensation</h2>
            <div className="kv"><span className="k">Base</span><span>{gbp(e.comp_base_gbp)}</span></div>
            <div className="kv"><span className="k">Total</span><span>{gbp(e.comp_total_gbp)}</span></div>
            {e.comp_equity_note && <div className="kv"><span className="k">Equity</span><span>{e.comp_equity_note}</span></div>}
          </Card>
          <Card>
            <h2 className="panel-title">Fit breakdown</h2>
            <FitBreakdown e={e} />
          </Card>
          {e.source_partner_ulid && (
            <Card>
              <h2 className="panel-title">Sourced by</h2>
              <a href={`/partners/${e.source_partner_ulid}`}>{e.source_partner_name}</a>
            </Card>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <Card>
            <h2 className="panel-title">Next step</h2>
            <p>{e.next_step ?? '—'}{e.next_step_date ? ` · ${e.next_step_date}` : ''}</p>
          </Card>
          <Card>
            <h2 className="panel-title">Timeline</h2>
            <ul className="timeline">
              {(e.log ?? []).map((l) => (
                <li key={l.ulid}>
                  <div className="when">{l.event_date}</div>
                  <div>{l.from_stage ? `${l.from_stage} → ${l.to_stage}` : l.event_type}{l.summary ? ` — ${l.summary}` : ''}</div>
                </li>
              ))}
              {(e.log ?? []).length === 0 && <li><span className="rationale">No events yet.</span></li>}
            </ul>
          </Card>
        </div>
      </div>

      <Card style={{ marginTop: 'var(--space-3)' }}>
        <h2 className="panel-title">Dossier &amp; prep notes</h2>
        {(e.notes ?? []).length === 0 ? <p className="rationale">No notes yet.</p> :
          (e.notes ?? []).map((n) => (
            <div key={n.ulid} className="kv"><span>{n.body}</span><span className="when">{n.created_at.slice(0, 10)}</span></div>
          ))}
      </Card>
    </div>
  );
}

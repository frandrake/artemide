import { useEffect, useState } from 'react';
import { apiGet, ApiError } from '../../lib/api';
import type { Org } from '../../lib/types';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Skeleton } from '../ui/Skeleton';
import { fitTone, titleCase, ulidFromPath } from './helpers';
import DocumentsPanel from './DocumentsPanel';
import './v12.css';

export default function OrgDetail() {
  const ulid = ulidFromPath('orgs');
  const [o, setO] = useState<Org | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ulid) { setError('Invalid URL'); setLoading(false); return; }
    apiGet<Org>(`/api/v1/orgs/${ulid}`)
      .then((d) => setO(d))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load.'))
      .finally(() => setLoading(false));
  }, [ulid]);

  if (loading) return <Skeleton height={240} />;
  if (error) return <p className="v12-error">{error}</p>;
  if (!o) return null;

  return (
    <div>
      <div className="detail-header">
        <h1>{o.name}</h1>
        <Badge tone="neutral">{o.watch_state}</Badge>
        {o.scale_band && <Badge tone="info">{titleCase(o.scale_band)}</Badge>}
      </div>
      {o.pertinence_note && <p className="v12-subhead">{o.pertinence_note}</p>}

      <Card style={{ margin: 'var(--space-3) 0' }}>
        <h2 className="panel-title">Engagements</h2>
        {(o.engagements ?? []).length === 0 ? <p className="rationale">No engagements yet.</p> : (
          <div className="v12-grid-2">
            {(o.engagements ?? []).map((e) => (
              <a key={e.ulid} href={`/engagements/${e.ulid}`} className="eng-card">
                <div className="role">{e.role_title}</div>
                <div className="meta">
                  <span className={`fit fit--${fitTone(e)}`}>fit {e.fit_score ?? '—'}</span>
                  <Badge tone="info">{e.stage}</Badge>
                </div>
              </a>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h2 className="panel-title">Dossier notes</h2>
        {(o.notes ?? []).length === 0 ? <p className="rationale">No notes yet.</p> :
          (o.notes ?? []).map((n) => (
            <div key={n.ulid} className="kv"><span>{n.body}</span><span className="when">{n.created_at.slice(0, 10)}</span></div>
          ))}
      </Card>

      {ulid && <DocumentsPanel entityType="org" entityUlid={ulid} />}
    </div>
  );
}

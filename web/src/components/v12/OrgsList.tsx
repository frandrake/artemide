import { useMemo } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { Org, WatchState } from '../../lib/types';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { titleCase } from './helpers';
import './v12.css';

const ORDER: WatchState[] = ['target', 'active', 'watch', 'parked', 'excluded'];

export default function OrgsList() {
  const { data, loading, error } = useFetch<Org[]>('/api/v1/orgs');

  const grouped = useMemo(() => {
    const g: Record<string, Org[]> = {};
    for (const s of ORDER) g[s] = [];
    for (const o of data ?? []) (g[o.watch_state] ??= []).push(o);
    return g;
  }, [data]);

  if (loading) return <Skeleton height={240} />;
  if (error) return <p className="v12-error">{error}</p>;
  if ((data ?? []).length === 0) {
    return <EmptyState title="No organisations yet." description="Add one via the API, MCP, or Radar." />;
  }

  return (
    <div>
      {ORDER.filter((s) => grouped[s].length > 0).map((state) => (
        <section key={state} style={{ marginBottom: 'var(--space-4)' }}>
          <h2 className="panel-title">{titleCase(state)} <span className="count">({grouped[state].length})</span></h2>
          <div className="v12-grid-2">
            {grouped[state].map((o) => (
              <a key={o.ulid} href={`/orgs/${o.ulid}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                <Card>
                  <div className="org" style={{ fontFamily: 'var(--font-serif)', fontWeight: 700, color: 'var(--slate-blue)' }}>{o.name}</div>
                  {o.sector && <div className="rationale">{o.sector}</div>}
                  <div className="meta" style={{ marginTop: 6, display: 'flex', gap: 'var(--space-1)' }}>
                    {o.scale_band && <Badge tone="neutral">{titleCase(o.scale_band)}</Badge>}
                  </div>
                </Card>
              </a>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

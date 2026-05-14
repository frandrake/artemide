import { useEffect, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiGet } from '../../lib/api';
import type { ContactLog, Firm } from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import StatusPill from '../ui/StatusPill';
import Badge from '../ui/Badge';
import Sparkline from './Sparkline';
import './PipelineOverview.css';

const SPARKLINE_MONTHS = 12;

function bucketContactsByMonth(contacts: ContactLog[]): number[] {
  const now = new Date();
  const counts = new Array(SPARKLINE_MONTHS).fill(0);
  const earliest = new Date(now.getFullYear(), now.getMonth() - (SPARKLINE_MONTHS - 1), 1);
  for (const c of contacts) {
    const d = new Date(c.contact_date);
    if (d < earliest) continue;
    const monthsAgo =
      (now.getFullYear() - d.getFullYear()) * 12 + (now.getMonth() - d.getMonth());
    if (monthsAgo < 0 || monthsAgo >= SPARKLINE_MONTHS) continue;
    counts[SPARKLINE_MONTHS - 1 - monthsAgo] += 1;
  }
  return counts;
}

export default function PipelineOverview() {
  const primary = useFetch<Firm[]>('/api/v1/firms?tier=primary');
  const specialist = useFetch<Firm[]>('/api/v1/firms?tier=specialist');
  const [sparklines, setSparklines] = useState<Record<string, number[]>>({});
  const [showSpecialist, setShowSpecialist] = useState(false);

  // Build sparkline data for primary firms once they load.
  useEffect(() => {
    if (!primary.data) return;
    let cancelled = false;
    (async () => {
      const pairs = await Promise.all(
        primary.data!.map(async (f) => {
          try {
            const cs = await apiGet<ContactLog[]>(
              `/api/v1/contacts?firm_ulid=${encodeURIComponent(f.ulid)}&limit=500`,
            );
            return [f.ulid, bucketContactsByMonth(cs)] as const;
          } catch {
            return [f.ulid, new Array(SPARKLINE_MONTHS).fill(0)] as const;
          }
        }),
      );
      if (!cancelled) setSparklines(Object.fromEntries(pairs));
    })();
    return () => { cancelled = true; };
  }, [primary.data]);

  return (
    <section className="pipeline" aria-labelledby="pipeline-h">
      <header className="pipeline__head">
        <h2 id="pipeline-h">Primary tier</h2>
        <p className="pipeline__sub">
          {primary.data ? `${primary.data.length} firms` : ''}
        </p>
      </header>

      {primary.loading && (
        <div className="pipeline__grid">
          {Array.from({ length: 5 }).map((_, i) => (
            <div className="pipeline__card pipeline__card--skeleton" key={i}>
              <Skeleton width="60%" height={20} />
              <Skeleton width="40%" height={14} />
              <Skeleton width="80%" height={14} />
            </div>
          ))}
        </div>
      )}

      {primary.error && (
        <div className="pipeline__error" role="alert">
          <p>Couldn't load primary tier: {primary.error}</p>
          <button type="button" onClick={primary.refresh}>Retry</button>
        </div>
      )}

      {primary.data && primary.data.length > 0 && (
        <div className="pipeline__grid">
          {primary.data.map((f) => {
            const accent = f.relationship_state === 'cold' || f.relationship_state === 'dormant';
            return (
              <a key={f.ulid} className="pipeline__card" href={`/firms/${f.ulid}`}>
                <h3 className="pipeline__name">{f.name}</h3>
                <div className="pipeline__meta">
                  {f.region && <Badge tone="neutral">{f.region}</Badge>}
                  <StatusPill state={f.relationship_state} />
                </div>
                <div className="pipeline__spark">
                  <Sparkline
                    data={sparklines[f.ulid] ?? new Array(SPARKLINE_MONTHS).fill(0)}
                    accent={accent}
                    ariaLabel={`${f.name} contact activity over 12 months`}
                  />
                </div>
              </a>
            );
          })}
        </div>
      )}

      {primary.data && primary.data.length === 0 && (
        <p className="pipeline__empty">No primary firms yet.</p>
      )}

      {specialist.data && specialist.data.length > 0 && (
        <details
          className="pipeline__specialist"
          open={showSpecialist}
          onToggle={(e) => setShowSpecialist(e.currentTarget.open)}
        >
          <summary>
            <span>+ {specialist.data.length} specialist firms</span>
          </summary>
          <ul className="pipeline__specialist-list">
            {specialist.data.map((f) => (
              <li key={f.ulid}>
                <a href={`/firms/${f.ulid}`}>{f.name}</a>
                {f.region && <span className="pipeline__specialist-region"> · {f.region}</span>}
                <StatusPill state={f.relationship_state} />
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { Firm, FirmTier, RelationshipState } from '../../lib/types';
import EmptyState from '../ui/EmptyState';
import Skeleton from '../ui/Skeleton';
import Select from '../ui/Select';
import FirmCard from './FirmCard';
import './FirmsList.css';

const TIER_ORDER: FirmTier[] = ['primary', 'specialist', 'ned'];

function buildPath(opts: { tier: FirmTier | 'all'; state: RelationshipState | 'all'; includeDeleted: boolean }): string {
  const params = new URLSearchParams();
  if (opts.tier !== 'all') params.set('tier', opts.tier);
  if (opts.state !== 'all') params.set('state', opts.state);
  if (opts.includeDeleted) params.set('include_deleted', 'true');
  const q = params.toString();
  return q ? `/api/v1/firms?${q}` : '/api/v1/firms';
}

export default function FirmsList() {
  const [tier, setTier] = useState<FirmTier | 'all'>('all');
  const [state, setState] = useState<RelationshipState | 'all'>('all');
  const [includeDeleted, setIncludeDeleted] = useState(false);

  const path = buildPath({ tier, state, includeDeleted });
  const { data, loading, error, refresh } = useFetch<Firm[]>(path);

  const grouped = useMemo(() => {
    const out: Record<FirmTier, Firm[]> = { primary: [], specialist: [], ned: [] };
    (data ?? []).forEach((f) => { out[f.tier].push(f); });
    return out;
  }, [data]);

  return (
    <div className="firms-list">
      <div className="firms-list__filters">
        <Select
          label="Tier"
          value={tier}
          onChange={(e) => setTier(e.currentTarget.value as FirmTier | 'all')}
        >
          <option value="all">All tiers</option>
          <option value="primary">Primary</option>
          <option value="specialist">Specialist</option>
          <option value="ned">NED</option>
        </Select>
        <Select
          label="State"
          value={state}
          onChange={(e) => setState(e.currentTarget.value as RelationshipState | 'all')}
        >
          <option value="all">Any state</option>
          <option value="warm">Warm</option>
          <option value="warming">Warming</option>
          <option value="cold">Cold</option>
          <option value="dormant">Dormant</option>
        </Select>
        <label className="firms-list__toggle">
          <input
            type="checkbox"
            checked={includeDeleted}
            onChange={(e) => setIncludeDeleted(e.currentTarget.checked)}
          />
          <span>Include deleted</span>
        </label>
      </div>

      {loading && (
        <div className="firms-list__grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div className="firms-list__card-skeleton" key={i}>
              <Skeleton width="60%" height={20} />
              <Skeleton width="40%" height={14} />
              <Skeleton width="80%" height={14} />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="firms-list__error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={refresh}>Retry</button>
        </div>
      )}

      {data && data.length === 0 && (
        <EmptyState
          title="No firms yet"
          description="Seed the firm directory before logging contacts."
          cta={
            <code className="firms-list__seed-cmd">uv run python scripts/seed_firms.py</code>
          }
        />
      )}

      {data && data.length > 0 && (
        <div className="firms-list__sections">
          {TIER_ORDER.map((t) => {
            const items = grouped[t];
            if (items.length === 0) return null;
            return (
              <section key={t}>
                <h2 className="firms-list__tier">{titleCase(t)} tier · {items.length}</h2>
                <div className="firms-list__grid">
                  {items.map((f) => <FirmCard key={f.ulid} firm={f} />)}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function titleCase(s: string): string {
  if (s === 'ned') return 'NED';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

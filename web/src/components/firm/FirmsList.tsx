import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost, ApiError } from '../../lib/api';
import type { Firm, FirmTier, RelationshipState } from '../../lib/types';
import EmptyState from '../ui/EmptyState';
import Skeleton from '../ui/Skeleton';
import Select from '../ui/Select';
import FirmCard from './FirmCard';
import RestoreConfirmModal from '../shared/RestoreConfirmModal';
import Toast from '../shared/Toast';
import { formatRelativeDate } from '../../lib/formatting';
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

  // Restore modal state
  const [restoreFirm, setRestoreFirm] = useState<Firm | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreError, setRestoreError] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<string | null>(null);

  const { active, deleted } = useMemo(() => {
    const all = data ?? [];
    return {
      active: all.filter((f) => !f.deleted_at),
      deleted: all.filter((f) => !!f.deleted_at),
    };
  }, [data]);

  const groupedActive = useMemo(() => {
    const out: Record<FirmTier, Firm[]> = { primary: [], specialist: [], ned: [] };
    active.forEach((f) => { out[f.tier].push(f); });
    return out;
  }, [active]);

  const groupedDeleted = useMemo(() => {
    const out: Record<FirmTier, Firm[]> = { primary: [], specialist: [], ned: [] };
    deleted.forEach((f) => { out[f.tier].push(f); });
    return out;
  }, [deleted]);

  async function handleRestoreConfirm() {
    if (!restoreFirm) return;
    setIsRestoring(true);
    setRestoreError(undefined);
    try {
      await apiPost(`/api/v1/firms/${restoreFirm.ulid}/restore`);
      setRestoreFirm(null);
      await refresh();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Restore failed.';
      setRestoreError(msg);
    } finally {
      setIsRestoring(false);
    }
  }

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
            const activeItems = groupedActive[t];
            const deletedItems = includeDeleted ? groupedDeleted[t] : [];
            if (activeItems.length === 0 && deletedItems.length === 0) return null;
            return (
              <section key={t}>
                <h2 className="firms-list__tier">{titleCase(t)} tier · {activeItems.length}</h2>
                {activeItems.length > 0 && (
                  <div className="firms-list__grid">
                    {activeItems.map((f) => <FirmCard key={f.ulid} firm={f} />)}
                  </div>
                )}
                {deletedItems.length > 0 && (
                  <div className="firms-list__deleted-section">
                    <p className="firms-list__deleted-label">DELETED</p>
                    <div className="firms-list__grid">
                      {deletedItems.map((f) => (
                        <DeletedFirmCard
                          key={f.ulid}
                          firm={f}
                          onRestore={() => { setRestoreError(undefined); setRestoreFirm(f); }}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      <RestoreConfirmModal
        entityType="firm"
        entityName={restoreFirm?.name ?? ''}
        isOpen={!!restoreFirm}
        isRestoring={isRestoring}
        error={restoreError}
        onConfirm={handleRestoreConfirm}
        onCancel={() => { setRestoreFirm(null); setRestoreError(undefined); }}
      />

      {toast && <Toast message={toast} tone="error" onDismiss={() => setToast(null)} />}
    </div>
  );
}

function DeletedFirmCard({ firm, onRestore }: { firm: Firm; onRestore: () => void }) {
  const deletedAgo = firm.deleted_at ? formatRelativeDate(firm.deleted_at) : '';
  return (
    <div className="firm-card firm-card--deleted">
      <h3 className="firm-card__name firm-card__name--deleted">{firm.name}</h3>
      <div className="firm-card__meta">
        <span className="firm-card__badge-muted">{firm.tier}</span>
        {firm.region && <span className="firm-card__badge-muted">{firm.region}</span>}
        <span className="firm-card__badge-muted">{firm.relationship_state}</span>
      </div>
      <p className="firm-card__deleted-note">deleted {deletedAgo}</p>
      <button type="button" className="firm-card__restore-btn" onClick={onRestore}>
        Restore
      </button>
    </div>
  );
}

function titleCase(s: string): string {
  if (s === 'ned') return 'NED';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

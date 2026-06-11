import clsx from 'clsx';
import { useMemo, useState } from 'react';
import { apiDelete, apiPost, ApiError } from '../../lib/api';
import { useFetch } from '../../lib/useFetch';
import type { CompComparison, CompScenario } from '../../lib/types';
import { gbp, titleCase } from '../v12/helpers';
import Badge from '../ui/Badge';
import Button from '../ui/Button';
import Card from '../ui/Card';
import EmptyState from '../ui/EmptyState';
import Skeleton from '../ui/Skeleton';
import ComparisonTable from './ComparisonTable';
import ScenarioForm from './ScenarioForm';
import './CompPage.css';

export function CompPage() {
  const list = useFetch<CompScenario[]>('/api/v1/comp-scenarios');
  // null = default (every non-baseline scenario); a Set once the user curates.
  const [selected, setSelected] = useState<Set<string> | null>(null);
  const [editing, setEditing] = useState<CompScenario | 'new' | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const scenarios = list.data ?? [];
  const baseline = scenarios.find((s) => s.is_baseline) ?? null;
  const others = scenarios.filter((s) => !s.is_baseline);

  const includedUlids = useMemo(
    () => (selected === null ? others.map((s) => s.ulid) : others.map((s) => s.ulid).filter((u) => selected.has(u))),
    [selected, others],
  );

  const comparePath = useMemo(() => {
    if (!baseline || includedUlids.length === 0) return null;
    const qs = includedUlids.map((u) => `scenario_ulid=${u}`).join('&');
    return `/api/v1/comp-scenarios/compare?${qs}`;
  }, [baseline, includedUlids]);

  const comparison = useFetch<CompComparison>(comparePath);

  function toggle(ulid: string) {
    setSelected((prev) => {
      const next = new Set(prev === null ? others.map((s) => s.ulid) : prev);
      if (next.has(ulid)) next.delete(ulid); else next.add(ulid);
      return next;
    });
  }

  async function refreshAll() {
    setEditing(null);
    await list.refresh();
    await comparison.refresh();
  }

  async function act(fn: () => Promise<unknown>) {
    setActionError(null);
    try {
      await fn();
      await refreshAll();
    } catch (e) {
      setActionError(e instanceof ApiError ? `${e.status}: ${e.message}` : 'Action failed.');
    }
  }

  const remove = (s: CompScenario) => {
    if (!window.confirm(`Delete scenario "${s.name}"?`)) return;
    void act(() => apiDelete(`/api/v1/comp-scenarios/${s.ulid}`));
  };
  const makeBaseline = (s: CompScenario) => {
    if (!window.confirm(`Make "${s.name}" the comparison baseline?`)) return;
    void act(() => apiPost(`/api/v1/comp-scenarios/${s.ulid}/baseline`));
  };

  if (list.loading) {
    return (
      <div className="comp-page" aria-busy="true">
        <div className="comp-rail">
          <Skeleton height={140} /><Skeleton height={140} /><Skeleton height={140} />
        </div>
        <Skeleton height={280} />
      </div>
    );
  }
  if (list.error) {
    return <p className="comp-error" role="alert">Could not load scenarios — {list.error}</p>;
  }

  return (
    <div className="comp-page">
      <div className="comp-toolbar">
        <Button onClick={() => setEditing('new')}>New scenario</Button>
        {actionError && <p className="comp-error" role="alert">{actionError}</p>}
      </div>

      <div className="comp-rail">
        {baseline && (
          <ScenarioCard
            key={baseline.ulid}
            scenario={baseline}
            onEdit={() => setEditing(baseline)}
          />
        )}
        {others.map((s) => (
          <ScenarioCard
            key={s.ulid}
            scenario={s}
            included={includedUlids.includes(s.ulid)}
            onToggle={() => toggle(s.ulid)}
            onEdit={() => setEditing(s)}
            onDelete={() => remove(s)}
            onMakeBaseline={() => makeBaseline(s)}
          />
        ))}
        {!baseline && others.length === 0 && (
          <EmptyState
            title="No scenarios yet"
            description="Create your baseline package, then add scenarios under discussion to compare."
            cta={<Button onClick={() => setEditing('new')}>New scenario</Button>}
          />
        )}
      </div>

      {baseline && others.length === 0 && (
        <EmptyState
          title="Nothing to compare yet"
          description="Add a scenario under discussion and it will appear side by side with the baseline."
        />
      )}
      {comparePath && comparison.loading && <Skeleton height={280} />}
      {comparePath && comparison.error && (
        <p className="comp-error" role="alert">Comparison failed — {comparison.error}</p>
      )}
      {comparison.data && !comparison.loading && <ComparisonTable comparison={comparison.data} />}
      {baseline && others.length > 0 && includedUlids.length === 0 && (
        <EmptyState title="No scenarios selected" description="Tick at least one scenario to compare it against the baseline." />
      )}

      {editing && (
        <ScenarioForm
          scenario={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => void refreshAll()}
        />
      )}
    </div>
  );
}

function ScenarioCard({
  scenario: s,
  included,
  onToggle,
  onEdit,
  onDelete,
  onMakeBaseline,
}: {
  scenario: CompScenario;
  included?: boolean;
  onToggle?: () => void;
  onEdit: () => void;
  onDelete?: () => void;
  onMakeBaseline?: () => void;
}) {
  return (
    <Card className={clsx('comp-card', s.is_baseline && 'comp-card--baseline')}>
      <div className="comp-card__head">
        <h3 className="comp-card__name">{s.name}</h3>
        {s.is_baseline
          ? <Badge tone="accent">Baseline</Badge>
          : <Badge tone="neutral">{titleCase(s.status)}</Badge>}
      </div>
      <p className="comp-card__total">{gbp(s.totals.total_gbp)}<span className="comp-card__total-label"> total</span></p>
      {s.engagement_ulid && (
        <p className="comp-card__engagement">
          {s.engagement_org_name ? `${s.engagement_org_name} — ` : ''}{s.engagement_role_title}
        </p>
      )}
      <div className="comp-card__actions">
        {onToggle && (
          <label className="comp-card__toggle">
            <input type="checkbox" checked={included ?? false} onChange={onToggle} /> Compare
          </label>
        )}
        <Button size="sm" variant="ghost" onClick={onEdit}>Edit</Button>
        {onMakeBaseline && <Button size="sm" variant="ghost" onClick={onMakeBaseline}>Set baseline</Button>}
        {onDelete && <Button size="sm" variant="ghost" className="comp-card__delete" onClick={onDelete}>Delete</Button>}
      </div>
    </Card>
  );
}

export default CompPage;

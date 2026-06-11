import clsx from 'clsx';
import type { CompComparison, CompScenario } from '../../lib/types';
import { gbp } from '../v12/helpers';

const ROWS: { key: string; label: string; total?: boolean }[] = [
  { key: 'base_gbp', label: 'Base salary' },
  { key: 'cash_bonus_gbp', label: 'Cash bonus' },
  { key: 'equity_gbp', label: 'Equity' },
  { key: 'pension_value_gbp', label: 'Pension value' },
  { key: 'healthcare_gbp', label: 'Healthcare' },
  { key: 'car_allowance_gbp', label: 'Car allowance' },
  { key: 'other_gbp', label: 'Other' },
  { key: 'total_cash_gbp', label: 'Total cash', total: true },
  { key: 'total_gbp', label: 'Total comp', total: true },
];

function scenarioValue(s: CompScenario, key: string): number {
  if (key in s.totals) return s.totals[key as keyof typeof s.totals];
  return (s[key as keyof CompScenario] as number | null) ?? 0;
}

function DeltaLine({ deltaGbp, deltaPct }: { deltaGbp: number; deltaPct: number | null }) {
  const tone = deltaGbp > 0 ? 'pos' : deltaGbp < 0 ? 'neg' : 'zero';
  const sign = deltaGbp > 0 ? '+' : deltaGbp < 0 ? '−' : '';
  const pct =
    deltaPct == null || deltaGbp === 0
      ? null
      : `${deltaPct > 0 ? '+' : '−'}${Math.abs(deltaPct)}%`;
  return (
    <span className={clsx('comp-delta', `comp-delta--${tone}`)}>
      {deltaGbp === 0 ? '=' : `${sign}${gbp(Math.abs(deltaGbp))}`}
      {pct && <span className="comp-delta__pct"> · {pct}</span>}
    </span>
  );
}

export function ComparisonTable({ comparison }: { comparison: CompComparison }) {
  const { baseline, scenarios } = comparison;
  return (
    <div className="comp-table-wrap">
      <table className="comp-table">
        <thead>
          <tr>
            <th scope="col">Component</th>
            <th scope="col">
              {baseline.name}
              <span className="comp-table__tag">Baseline</span>
            </th>
            {scenarios.map((s) => (
              <th scope="col" key={s.ulid}>
                {s.name}
                <span className="comp-table__tag comp-table__tag--muted">{s.status}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map(({ key, label, total }) => (
            <tr key={key} className={clsx(total && 'comp-table__row--total')}>
              <th scope="row">
                {label}
                {key === 'pension_value_gbp' && baseline.pension_pct != null && (
                  <span className="comp-table__note"> (baseline {baseline.pension_pct}%)</span>
                )}
              </th>
              <td>{gbp(scenarioValue(baseline, key))}</td>
              {scenarios.map((s) => {
                const d = s.deltas[key];
                return (
                  <td key={s.ulid}>
                    <span className="comp-table__value">{gbp(d ? d.scenario : scenarioValue(s, key))}</span>
                    {d && <DeltaLine deltaGbp={d.delta_gbp} deltaPct={d.delta_pct} />}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {(baseline.equity_note || baseline.benefits_note || scenarios.some((s) => s.equity_note || s.benefits_note)) && (
        <div className="comp-notes">
          {[baseline, ...scenarios].map((s) =>
            s.equity_note || s.benefits_note ? (
              <p key={s.ulid} className="comp-notes__item">
                <strong>{s.name}:</strong>{' '}
                {[s.equity_note, s.benefits_note].filter(Boolean).join(' · ')}
              </p>
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}

export default ComparisonTable;

import { useMemo } from 'react';
import './DiffView.css';

export interface DiffViewProps {
  before: unknown;
  after: unknown;
}

interface Row {
  key: string;
  beforeText: string | null;
  afterText: string | null;
  changed: boolean;
}

function flatten(prefix: string, value: unknown, into: Map<string, string>): void {
  if (value === null || value === undefined) {
    into.set(prefix || '(root)', String(value));
    return;
  }
  if (typeof value !== 'object') {
    into.set(prefix || '(root)', String(value));
    return;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) into.set(prefix || '(root)', '[]');
    else if (value.length > 10) into.set(prefix, `[${value.length} items, collapsed]`);
    else value.forEach((v, i) => flatten(`${prefix}[${i}]`, v, into));
    return;
  }
  const entries = Object.entries(value as Record<string, unknown>);
  if (entries.length === 0) into.set(prefix || '(root)', '{}');
  for (const [k, v] of entries) {
    flatten(prefix ? `${prefix}.${k}` : k, v, into);
  }
}

function buildRows(before: unknown, after: unknown): Row[] {
  const b = new Map<string, string>();
  const a = new Map<string, string>();
  flatten('', before, b);
  flatten('', after, a);
  const keys = Array.from(new Set([...b.keys(), ...a.keys()])).sort();
  return keys.map((k) => {
    const bv = b.get(k) ?? null;
    const av = a.get(k) ?? null;
    return { key: k, beforeText: bv, afterText: av, changed: bv !== av };
  });
}

export function DiffView({ before, after }: DiffViewProps) {
  const rows = useMemo(() => buildRows(before, after), [before, after]);

  if (rows.length === 0) {
    return <p className="diff__empty">No payload recorded.</p>;
  }

  return (
    <div className="diff" role="table" aria-label="Audit diff">
      <div className="diff__head" role="row">
        <div role="columnheader">Field</div>
        <div role="columnheader">Before</div>
        <div role="columnheader">After</div>
      </div>
      {rows.map((r) => (
        <div
          key={r.key}
          role="row"
          className={`diff__row${r.changed ? ' is-changed' : ' is-unchanged'}`}
        >
          <div className="diff__key" role="cell">{r.key}</div>
          <div className="diff__before" role="cell">{r.beforeText ?? <em>—</em>}</div>
          <div className="diff__after" role="cell">{r.afterText ?? <em>—</em>}</div>
        </div>
      ))}
    </div>
  );
}

export default DiffView;

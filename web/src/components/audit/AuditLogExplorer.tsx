import { useEffect, useState } from 'react';
import { apiGet } from '../../lib/api';
import type { AuditLogRecord } from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import Select from '../ui/Select';
import Input from '../ui/Input';
import Button from '../ui/Button';
import Badge from '../ui/Badge';
import DiffView from './DiffView';
import { formatAbsoluteDate } from '../../lib/formatting';
import './AuditLogExplorer.css';

const PAGE_SIZE = 50;

const ACTIONS = ['', 'create', 'update', 'delete', 'restore', 'log_contact', 'import', 'note', 'plan', 'rotate_token'];
const TRANSPORTS = ['', 'rest', 'mcp', 'cli', 'system', 'web', 'api'];

interface Filters {
  entity_type: string;
  entity_id: string;
  actor: string;
  action: string;
  transport: string;
}

const EMPTY: Filters = { entity_type: '', entity_id: '', actor: '', action: '', transport: '' };

function buildQuery(f: Filters, offset: number): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v) params.set(k, v);
  params.set('limit', String(PAGE_SIZE));
  params.set('offset', String(offset));
  return params.toString();
}

export default function AuditLogExplorer() {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [offset, setOffset] = useState(0);
  const [entries, setEntries] = useState<AuditLogRecord[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiGet<AuditLogRecord[]>(`/api/v1/audit/log?${buildQuery(filters, offset)}`)
      .then((d) => { if (!cancelled) setEntries(d); })
      .catch((e) => { if (!cancelled) setError(e?.message ?? 'Failed to load.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [filters, offset]);

  function update<K extends keyof Filters>(k: K, v: Filters[K]) {
    setFilters((cur) => ({ ...cur, [k]: v }));
    setOffset(0);
  }

  return (
    <div className="audit-log">
      <header className="audit-log__head">
        <h1>Audit log</h1>
        <p className="audit-log__sub">Every mutation, every transport.</p>
      </header>

      <section className="audit-log__filters">
        <Input
          label="Entity ULID"
          value={filters.entity_id}
          onChange={(e) => update('entity_id', e.currentTarget.value.trim().toUpperCase())}
          placeholder="01..."
        />
        <Input
          label="Entity type"
          value={filters.entity_type}
          onChange={(e) => update('entity_type', e.currentTarget.value.trim())}
          placeholder="firm / partner / contact"
        />
        <Select
          label="Action"
          value={filters.action}
          onChange={(e) => update('action', e.currentTarget.value)}
        >
          {ACTIONS.map((a) => <option key={a} value={a}>{a || 'any'}</option>)}
        </Select>
        <Select
          label="Transport"
          value={filters.transport}
          onChange={(e) => update('transport', e.currentTarget.value)}
        >
          {TRANSPORTS.map((t) => <option key={t} value={t}>{t || 'any'}</option>)}
        </Select>
        <Input
          label="Actor"
          value={filters.actor}
          onChange={(e) => update('actor', e.currentTarget.value)}
          placeholder="FF"
        />
      </section>

      {loading && <Skeleton width="100%" height={200} />}
      {error && <p className="audit-log__error" role="alert">{error}</p>}

      {entries && entries.length === 0 && (
        <p className="audit-log__empty">No audit entries match these filters.</p>
      )}

      {entries && entries.length > 0 && (
        <table className="audit-log__table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Transport</th>
              <th>Action</th>
              <th>Entity</th>
              <th>ULID</th>
              <th>Actor</th>
              <th aria-label="expand"></th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => {
              const open = expanded === e.ulid;
              const payload = parsePayload(e.payload);
              return (
                <>
                  <tr key={e.ulid} className="audit-log__row" onClick={() => setExpanded(open ? null : e.ulid)}>
                    <td>{formatAbsoluteDate(e.timestamp)}</td>
                    <td><Badge tone="neutral">{e.transport}</Badge></td>
                    <td><Badge tone={e.action === 'delete' ? 'accent' : 'info'}>{e.action}</Badge></td>
                    <td>{e.entity_type}</td>
                    <td><CopyableUlid value={e.entity_id} /></td>
                    <td>{e.actor}</td>
                    <td>{open ? '▾' : '▸'}</td>
                  </tr>
                  {open && (
                    <tr key={`${e.ulid}-diff`} className="audit-log__diff-row">
                      <td colSpan={7}>
                        <DiffView before={payload?.before ?? null} after={payload?.after ?? null} />
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      )}

      <div className="audit-log__pager">
        <Button
          variant="ghost"
          size="sm"
          disabled={offset === 0 || loading}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        >Prev</Button>
        <span>Offset {offset}–{offset + (entries?.length ?? 0)}</span>
        <Button
          variant="ghost"
          size="sm"
          disabled={loading || (entries && entries.length < PAGE_SIZE) || false}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >Next</Button>
      </div>
    </div>
  );
}

function parsePayload(raw: string | null): { before?: unknown; after?: unknown } | null {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

function CopyableUlid({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const short = value.length > 12 ? `${value.slice(0, 6)}…${value.slice(-4)}` : value;
  function copy(e: React.MouseEvent) {
    e.stopPropagation();
    navigator.clipboard?.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  }
  return (
    <button
      type="button"
      className="audit-log__copy"
      onClick={copy}
      title={value}
      aria-label={`Copy ULID ${value}`}
    >{copied ? 'copied' : short}</button>
  );
}

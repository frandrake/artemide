import { useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { AuditReport, CoverageEntry } from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import Button from '../ui/Button';
import StatusPill from '../ui/StatusPill';
import './AuditReportView.css';

export default function AuditReportView() {
  const { data, loading, error, refresh } = useFetch<AuditReport>('/api/v1/audit/report');
  const [crossedOut, setCrossedOut] = useState<Set<number>>(new Set());

  return (
    <div className="audit-report">
      <header className="audit-report__head">
        <div>
          <h1>Audit report</h1>
          <p className="audit-report__sub">
            {data ? `as of ${formatTs(data.generated_at)}` : ' '}
          </p>
        </div>
        <div className="audit-report__actions">
          <Button variant="ghost" size="sm" onClick={refresh}>Refresh</Button>
          <Button variant="secondary" size="sm" onClick={() => window.print()}>Print</Button>
        </div>
      </header>

      {loading && <Skeleton width="100%" height={120} />}
      {error && <p className="audit-report__error" role="alert">{error}</p>}

      {data && (
        <>
          <section className="audit-report__card">
            <h2>Summary actions</h2>
            {data.summary_actions.length === 0
              ? <p className="audit-report__empty">No urgent actions.</p>
              : (
                <ol className="audit-report__actions-list">
                  {data.summary_actions.map((line, i) => {
                    const struck = crossedOut.has(i);
                    return (
                      <li
                        key={i}
                        className={struck ? 'is-struck' : ''}
                        onClick={() => {
                          const next = new Set(crossedOut);
                          if (struck) next.delete(i); else next.add(i);
                          setCrossedOut(next);
                        }}
                      >
                        <span>{line}</span>
                      </li>
                    );
                  })}
                </ol>
              )}
          </section>

          <CoverageSection title="Primary tier coverage" rows={data.primary_tier_coverage} />
          <CoverageSection title="Specialist tier coverage" rows={data.specialist_tier_coverage} />

          <section className="audit-report__card">
            <h2>Dormant relationships</h2>
            {data.dormant_relationships.length === 0
              ? <p className="audit-report__empty">No dormant partners.</p>
              : (
                <ul className="audit-report__list">
                  {data.dormant_relationships.map((d) => (
                    <li key={d.partner_ulid}>
                      <a className="audit-report__link" href={`/partners/${d.partner_ulid}`}>{d.partner_name}</a>
                      <span className="audit-report__muted"> · {d.firm_name} · {d.tier}</span>
                      <span className="audit-report__metric">{d.days_since_last_contact}d dormant</span>
                    </li>
                  ))}
                </ul>
              )}
          </section>

          <section className="audit-report__card">
            <h2>Open follow-ups</h2>
            {data.open_follow_ups.length === 0
              ? <p className="audit-report__empty">All follow-ups resolved.</p>
              : (
                <ul className="audit-report__list">
                  {data.open_follow_ups.map((f) => (
                    <li key={f.partner_ulid}>
                      <a className="audit-report__link" href={`/partners/${f.partner_ulid}`}>{f.partner_name}</a>
                      <span className="audit-report__muted"> · {f.firm_name}</span>
                      <ul className="audit-report__sublist">
                        {f.items.map((it, i) => <li key={i}>{it}</li>)}
                      </ul>
                    </li>
                  ))}
                </ul>
              )}
          </section>

          <section className="audit-report__card">
            <h2>Reciprocity imbalances</h2>
            {data.reciprocity_imbalances.length === 0
              ? <p className="audit-report__empty">Relationships balanced.</p>
              : (
                <ul className="audit-report__list">
                  {data.reciprocity_imbalances.map((r) => (
                    <li key={r.partner_ulid}>
                      <a className="audit-report__link" href={`/partners/${r.partner_ulid}`}>{r.partner_name}</a>
                      <span className="audit-report__muted"> · {r.firm_name}</span>
                      <span className="audit-report__metric">given {r.given} · received {r.received}</span>
                    </li>
                  ))}
                </ul>
              )}
          </section>
        </>
      )}
    </div>
  );
}

function CoverageSection({ title, rows }: { title: string; rows: CoverageEntry[] }) {
  const total = rows.length;
  const withPartner = rows.filter((r) => r.has_active_partner).length;
  const flagged = rows.filter((r) => r.flagged);

  return (
    <section className="audit-report__card">
      <h2>{title}</h2>
      <div className="audit-report__stats">
        <div><strong>{total}</strong> firms</div>
        <div><strong>{withPartner}</strong> with active partner</div>
        <div><strong>{flagged.length}</strong> flagged</div>
      </div>

      <ul className="audit-report__list">
        {rows.map((r) => (
          <li key={r.firm_ulid} className={r.flagged ? 'is-flagged' : ''}>
            <a className="audit-report__link" href={`/firms/${r.firm_ulid}`}>{r.firm_name}</a>
            <StatusPill state={r.relationship_state} />
            <span className="audit-report__muted">
              {r.days_since_last_contact == null
                ? 'no contact on record'
                : `${r.days_since_last_contact}d since last contact`}
            </span>
            {r.flagged && r.note && (
              <span className="audit-report__note">{r.note}</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatTs(iso: string): string {
  try {
    return new Date(iso).toUTCString();
  } catch {
    return iso;
  }
}

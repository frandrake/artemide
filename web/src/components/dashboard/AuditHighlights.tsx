import { useFetch } from '../../lib/useFetch';
import type { AuditReport } from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import './AuditHighlights.css';

export default function AuditHighlights() {
  const { data, loading, error, refresh } = useFetch<AuditReport>('/api/v1/audit/report');

  return (
    <section className="audit-highlights" aria-labelledby="audit-h">
      <header className="audit-highlights__head">
        <h2 id="audit-h">Audit highlights</h2>
        <a className="audit-highlights__more" href="/audit">View full audit →</a>
      </header>

      {loading && (
        <div className="audit-highlights__list">
          {Array.from({ length: 3 }).map((_, i) => (
            <div className="audit-highlights__row audit-highlights__row--skeleton" key={i}>
              <Skeleton width="80%" height={18} />
              <Skeleton width="60%" height={14} />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="audit-highlights__error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={refresh}>Retry</button>
        </div>
      )}

      {data && (
        <ul className="audit-highlights__list">
          {data.summary_actions.slice(0, 3).map((line, i) => (
            <li className="audit-highlights__row" key={i}>
              <p className="audit-highlights__action">{line}</p>
            </li>
          ))}
          {data.summary_actions.length === 0 && (
            <li className="audit-highlights__row">
              <p className="audit-highlights__action">No urgent actions.</p>
            </li>
          )}
        </ul>
      )}
    </section>
  );
}

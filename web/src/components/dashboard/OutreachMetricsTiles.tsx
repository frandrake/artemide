import { useFetch } from '../../lib/useFetch';
import type { OutreachVolumePoint, ResponseRate, PlanExecution, ReciprocityPartner } from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import './OutreachMetricsTiles.css';

interface PipelineFunnel {
  researched: number;
  drafted: number;
  sent: number;
  replied: number;
  met: number;
  ongoing: number;
  paused: number;
  dropped: number;
}

export default function OutreachMetricsTiles() {
  const volume = useFetch<{ buckets: OutreachVolumePoint[]; granularity: string }>(
    '/api/v1/analytics/outreach-volume?granularity=week'
  );
  const rate = useFetch<ResponseRate>('/api/v1/analytics/response-rate');
  const plan = useFetch<PlanExecution>('/api/v1/analytics/plan-execution');
  const funnel = useFetch<PipelineFunnel>('/api/v1/analytics/pipeline-funnel');
  const recip = useFetch<ReciprocityPartner[]>('/api/v1/analytics/reciprocity-balance');

  const totalVolume = (volume.data?.buckets ?? []).reduce((acc, b) => acc + b.count, 0);

  return (
    <div className="metrics-tiles">
      <div className="metric-tile">
        <div className="metric-tile__label">Outreach volume (90d)</div>
        <div className="metric-tile__value">
          {volume.loading ? <Skeleton width="60%" height={28} /> : totalVolume}
        </div>
        <div className="metric-tile__sub">{(volume.data?.buckets ?? []).length} weekly buckets</div>
      </div>

      <div className="metric-tile">
        <div className="metric-tile__label">Response rate (30d)</div>
        <div className="metric-tile__value">
          {rate.loading ? <Skeleton width="50%" height={28} /> : `${Math.round((rate.data?.rate ?? 0) * 100)}%`}
        </div>
        <div className="metric-tile__sub">
          {rate.data ? `${rate.data.incoming} in / ${rate.data.sent} out` : ''}
        </div>
      </div>

      <div className="metric-tile">
        <div className="metric-tile__label">Plan execution (60d window)</div>
        <div className="metric-tile__value">
          {plan.loading ? <Skeleton width="50%" height={28} /> : `${Math.round((plan.data?.percent ?? 0) * 100)}%`}
        </div>
        <div className="metric-tile__sub">
          {plan.data ? `${plan.data.complete}/${plan.data.total} complete` : ''}
        </div>
      </div>

      <div className="metric-tile metric-tile--wide">
        <div className="metric-tile__label">Pipeline funnel</div>
        {funnel.loading ? (
          <Skeleton width="100%" height={28} />
        ) : funnel.data && (
          <ul className="funnel">
            {(['researched', 'drafted', 'sent', 'replied', 'met', 'ongoing', 'paused', 'dropped'] as const).map(s => (
              <li key={s} className="funnel__item">
                <span className="funnel__count">{funnel.data?.[s] ?? 0}</span>
                <span className="funnel__label">{s}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="metric-tile metric-tile--wide">
        <div className="metric-tile__label">Reciprocity imbalances (top 5)</div>
        {recip.loading ? <Skeleton width="100%" height={28} /> : (
          <ul className="recip">
            {(recip.data ?? []).filter(r => r.given !== 0 || r.received !== 0).slice(0, 5).map(r => (
              <li key={r.partner_ulid} className="recip__row">
                <a className="recip__name" href={`/partners/${r.partner_ulid}`}>{r.partner_name}</a>
                <span className="recip__firm">{r.firm_name}</span>
                <span className="recip__bal">
                  <span className="recip__given">↑{r.given}</span>
                  <span className="recip__sep">·</span>
                  <span className="recip__recv">↓{r.received}</span>
                  <span className={`recip__delta recip__delta--${r.balance >= 0 ? 'pos' : 'neg'}`}>
                    {r.balance > 0 ? `+${r.balance}` : r.balance}
                  </span>
                </span>
              </li>
            ))}
            {recip.data && recip.data.every(r => r.given === 0 && r.received === 0) && (
              <li className="recip__empty">No value-exchange logged yet.</li>
            )}
          </ul>
        )}
      </div>
    </div>
  );
}

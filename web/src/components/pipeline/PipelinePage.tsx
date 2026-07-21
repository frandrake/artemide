import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost, ApiError } from '../../lib/api';
import type { FirmTier, OutreachStage, PipelineCard, PipelineSnapshot } from '../../lib/types';
import Select from '../ui/Select';
import Skeleton from '../ui/Skeleton';
import './PipelinePage.css';

const STAGES: OutreachStage[] = [
  'researched', 'drafted', 'sent', 'replied', 'met', 'ongoing', 'paused', 'dropped',
];

const STAGE_LABEL: Record<OutreachStage, string> = {
  researched: 'Researched',
  drafted: 'Drafted',
  sent: 'Sent',
  replied: 'Replied',
  met: 'Met',
  ongoing: 'Ongoing',
  paused: 'Paused',
  dropped: 'Dropped',
};

export default function PipelinePage() {
  const [tier, setTier] = useState<FirmTier | 'all'>('all');
  const [strategic, setStrategic] = useState<string>('all');

  const path = useMemo(() => {
    const params = new URLSearchParams();
    if (tier !== 'all') params.set('tier', tier);
    if (strategic !== 'all') params.set('strategic_relevance', strategic);
    const q = params.toString();
    return q ? `/api/v1/pipeline?${q}` : '/api/v1/pipeline';
  }, [tier, strategic]);

  const { data, loading, error, refresh } = useFetch<PipelineSnapshot>(path);

  const [dragging, setDragging] = useState<{ ulid: string; from: OutreachStage } | null>(null);
  const [dropError, setDropError] = useState<string | null>(null);

  async function onDrop(stage: OutreachStage) {
    if (!dragging) return;
    if (dragging.from === stage) { setDragging(null); return; }
    const moving = dragging;
    setDragging(null);
    try {
      await apiPost(`/api/v1/partners/${moving.ulid}/outreach-stage`, { stage });
      setDropError(null);
      await refresh();
    } catch (e) {
      setDropError(
        e instanceof ApiError ? `Couldn't move card: ${e.message}` : "Couldn't move card — please retry.",
      );
      await refresh(); // resync the board to the server's truth
    }
  }

  return (
    <div className="pipeline-page">
      <div className="pipeline-page__filters">
        <Select label="Tier" value={tier} onChange={(e) => setTier(e.currentTarget.value as FirmTier | 'all')}>
          <option value="all">All tiers</option>
          <option value="primary">Primary</option>
          <option value="specialist">Specialist</option>
        </Select>
        <Select label="Strategic relevance" value={strategic} onChange={(e) => setStrategic(e.currentTarget.value)}>
          <option value="all">All</option>
          <option value="HIGH">HIGH</option>
          <option value="MEDIUM">MEDIUM</option>
          <option value="LOW">LOW</option>
        </Select>
      </div>

      {loading && <Skeleton width="100%" height={300} />}

      {error && !loading && (
        <div className="pipeline-page__error" role="alert">
          <span>Couldn't load the pipeline. {error}</span>
          <button type="button" onClick={() => refresh()}>Retry</button>
        </div>
      )}

      {dropError && (
        <div className="pipeline-page__error" role="alert">{dropError}</div>
      )}

      {!loading && !error && data && (
        <div className="pipeline-board">
          {STAGES.map(stage => (
            <PipelineColumn
              key={stage}
              stage={stage}
              cards={data.stages[stage] ?? []}
              dragging={dragging}
              onDragStart={(ulid) => setDragging({ ulid, from: stage })}
              onDrop={() => onDrop(stage)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface ColProps {
  stage: OutreachStage;
  cards: PipelineCard[];
  dragging: { ulid: string; from: OutreachStage } | null;
  onDragStart: (ulid: string) => void;
  onDrop: () => void;
}

function PipelineColumn({ stage, cards, dragging, onDragStart, onDrop }: ColProps) {
  return (
    <div
      className={`pipeline-col${dragging && dragging.from !== stage ? ' is-target' : ''}`}
      onDragOver={(e) => { e.preventDefault(); }}
      onDrop={(e) => { e.preventDefault(); onDrop(); }}
    >
      <header className="pipeline-col__header">
        <span className="pipeline-col__name">{STAGE_LABEL[stage]}</span>
        <span className="pipeline-col__count">{cards.length}</span>
      </header>
      <div className="pipeline-col__body">
        {cards.map(c => (
          <a
            key={c.partner_ulid}
            href={`/partners/${c.partner_ulid}`}
            className="pipeline-card"
            draggable
            onDragStart={(e) => {
              e.dataTransfer.effectAllowed = 'move';
              onDragStart(c.partner_ulid);
            }}
          >
            <div className="pipeline-card__name">{c.partner_name}</div>
            <div className="pipeline-card__firm">{c.firm_name}</div>
            <div className="pipeline-card__meta">
              {c.strategic_relevance && (
                <span className={`pipeline-card__chip pipeline-card__chip--rel-${c.strategic_relevance}`}>
                  {c.strategic_relevance}
                </span>
              )}
              {c.ned_gateway && (
                <span className="pipeline-card__chip pipeline-card__chip--ned">Board-practice contact</span>
              )}
            </div>
            {c.sent_count > 0 && (
              <div className="pipeline-card__sent">{c.sent_count} sent</div>
            )}
          </a>
        ))}
      </div>
    </div>
  );
}

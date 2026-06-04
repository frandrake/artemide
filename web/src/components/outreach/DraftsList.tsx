import { useMemo, useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import type { DraftStatus, OutreachDraftRecord } from '../../lib/types';
import Select from '../ui/Select';
import Skeleton from '../ui/Skeleton';
import EmptyState from '../ui/EmptyState';
import DraftEditor from './DraftEditor';
import './DraftsList.css';

export default function DraftsList() {
  const [statusFilter, setStatusFilter] = useState<DraftStatus | 'all'>('all');

  const path = useMemo(() => {
    const params = new URLSearchParams();
    if (statusFilter !== 'all') params.set('status', statusFilter);
    const q = params.toString();
    return q ? `/api/v1/outreach/drafts?${q}` : '/api/v1/outreach/drafts';
  }, [statusFilter]);

  const drafts = useFetch<OutreachDraftRecord[]>(path);

  const [editing, setEditing] = useState<{ partnerUlid: string; draftUlid: string } | null>(null);

  function openDraft(draft: OutreachDraftRecord) {
    // The list response now carries partner_ulid (injected server-side), so the
    // editor can render templates for the right partner.
    setEditing({ partnerUlid: draft.partner_ulid ?? '', draftUlid: draft.ulid });
  }

  return (
    <div className="drafts-list-page">
      <div className="drafts-list-page__filters">
        <Select
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.currentTarget.value as DraftStatus | 'all')}
        >
          <option value="all">All</option>
          <option value="draft">Draft</option>
          <option value="ready">Ready</option>
          <option value="sent">Sent</option>
          <option value="archived">Archived</option>
        </Select>
      </div>

      {drafts.loading && <Skeleton width="100%" height={120} />}
      {drafts.data && drafts.data.length === 0 && (
        <EmptyState
          title="No drafts yet"
          description="Open a partner detail page and click '+ New draft' to start one."
        />
      )}
      {drafts.data && drafts.data.length > 0 && (
        <ul className="drafts-list">
          {drafts.data.map(d => (
            <li key={d.ulid} className="drafts-list__row">
              <button
                type="button"
                className="drafts-list__row-button"
                onClick={() => openDraft(d)}
              >
                <span className={`drafts-list__status drafts-list__status--${d.status}`}>
                  {d.status}
                </span>
                <span className="drafts-list__channel">{d.channel}</span>
                <span className="drafts-list__subject">{d.subject || '(no subject)'}</span>
                <span className="drafts-list__version">v{d.version}</span>
                <span className="drafts-list__updated">
                  {new Date(d.updated_at).toLocaleDateString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <DraftEditor
          partnerUlid={editing.partnerUlid}
          draftUlid={editing.draftUlid}
          isOpen={!!editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); drafts.refresh(); }}
        />
      )}
    </div>
  );
}

import { useState } from 'react';
import { apiPost, apiPatch, ApiError } from '../../lib/api';
import { useFetch } from '../../lib/useFetch';
import type { Message } from '../../lib/types';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import './v12.css';

function MessageRow({ m, onChange }: { m: Message; onChange: () => void }) {
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(m.body);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setErr(null);
    try { await fn(); onChange(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : 'Failed.'); setBusy(false); }
  }

  return (
    <details className="msg-row">
      <summary>
        <span>
          <strong>{m.kind ?? 'message'}</strong>{m.recipient_hint ? ` · ${m.recipient_hint}` : ''}
          {m.partner_name ? ` · ${m.partner_name}` : ''}
        </span>
        <Badge tone={m.status === 'edited' ? 'accent' : 'info'}>{m.status}</Badge>
      </summary>
      <div className="msg-body-wrap">
        {m.rationale && <p className="rationale">{m.rationale}</p>}
        {m.subject && <p><strong>{m.subject}</strong></p>}
        {editing ? (
          <textarea className="msg-body" style={{ width: '100%' }} rows={6}
                    value={body} onChange={(e) => setBody(e.target.value)} />
        ) : (
          <div className="msg-body">{m.body}</div>
        )}
        {err && <p className="v12-error">{err}</p>}
        <div className="msg-actions">
          {editing ? (
            <>
              <Button size="sm" loading={busy}
                      onClick={() => act(async () => { await apiPatch(`/api/v1/messages/${m.ulid}`, { body }); setEditing(false); })}>
                Save edit
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setBody(m.body); }}>Cancel</Button>
            </>
          ) : (
            <>
              <Button size="sm" variant="primary" loading={busy}
                      onClick={() => act(() => apiPost(`/api/v1/messages/${m.ulid}/approve`))}>
                Approve
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>Edit</Button>
              <Button size="sm" variant="ghost" loading={busy}
                      onClick={() => act(() => apiPost(`/api/v1/messages/${m.ulid}/discard`))}>
                Discard
              </Button>
            </>
          )}
        </div>
      </div>
    </details>
  );
}

export default function ApprovalInbox() {
  const { data, loading, error, refresh } = useFetch<Message[]>('/api/v1/messages?status=proposed');

  if (loading) return <Skeleton height={200} />;
  if (error) return <p className="v12-error">{error}</p>;
  const items = data ?? [];
  if (items.length === 0) {
    return <EmptyState title="Nothing awaiting approval." />;
  }
  return (
    <div>
      {items.map((m) => <MessageRow key={m.ulid} m={m} onChange={refresh} />)}
    </div>
  );
}

import { useEffect, useRef, useState } from 'react';
import { apiGet, apiUpload, apiDelete, ApiError } from '../../lib/api';
import type { Attachment, AttachmentEntityType, AttachmentKind } from '../../lib/types';
import { bytes } from '../../lib/formatting';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Select } from '../ui/Select';
import { EmptyState } from '../ui/EmptyState';
import Toast from '../shared/Toast';
import { titleCase } from './helpers';

const KINDS: AttachmentKind[] = ['cv', 'profile', 'job_spec', 'transcript_file', 'reference', 'other'];

interface Props {
  entityType: AttachmentEntityType;
  entityUlid: string;
}

export default function DocumentsPanel({ entityType, entityUlid }: Props) {
  const [items, setItems] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [kind, setKind] = useState<AttachmentKind>('other');
  const [dragging, setDragging] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const listPath = `/api/v1/attachments?entity_type=${entityType}&entity_ulid=${entityUlid}`;

  async function load() {
    setLoading(true);
    try {
      setItems(await apiGet<Attachment[]>(listPath));
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : 'Failed to load documents.');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [entityType, entityUlid]);

  async function upload(file: File) {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('entity_type', entityType);
      fd.append('entity_ulid', entityUlid);
      fd.append('kind', kind);
      await apiUpload(listPath.split('?')[0], fd);
      await load();
      setToast('Uploaded.');
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : 'Upload failed.');
    } finally {
      setBusy(false);
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) upload(f);
    e.target.value = '';
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) upload(f);
  }

  async function remove(ulid: string) {
    setBusy(true);
    try {
      await apiDelete(`/api/v1/attachments/${ulid}`);
      setConfirm(null);
      await load();
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : 'Delete failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card style={{ marginTop: 'var(--space-3)' }}>
      <h2 className="panel-title">Documents</h2>

      <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'flex-end', marginBottom: 'var(--space-2)' }}>
        <Select label="Kind" value={kind} onChange={(e) => setKind(e.target.value as AttachmentKind)}>
          {KINDS.map((k) => <option key={k} value={k}>{titleCase(k)}</option>)}
        </Select>
        <Button loading={busy} onClick={() => fileInput.current?.click()}>Upload file</Button>
        <input ref={fileInput} type="file" hidden onChange={onPick} />
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        style={{
          border: `1px dashed ${dragging ? 'var(--color-primary, #4A5E7C)' : 'var(--color-border, #d6dae0)'}`,
          borderRadius: 4,
          padding: 'var(--space-3)',
          textAlign: 'center',
          marginBottom: 'var(--space-3)',
        }}
      >
        <span className="rationale">Drag &amp; drop a file here (PDF, DOCX, TXT, MD, PNG, JPEG · max 25 MB)</span>
      </div>

      {loading ? <p className="rationale">Loading…</p>
        : items.length === 0 ? <EmptyState title="No documents yet" description="Upload a CV, profile, or job spec." />
          : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {items.map((a) => (
                <li key={a.ulid} className="kv" style={{ alignItems: 'center', gap: 'var(--space-2)' }}>
                  <span style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center', minWidth: 0 }}>
                    <Badge tone="info">{titleCase(a.kind)}</Badge>
                    <a href={`/api/v1/attachments/${a.ulid}/content`} download>{a.filename}</a>
                    <span className="rationale">{bytes(a.byte_size)}</span>
                  </span>
                  {confirm === a.ulid ? (
                    <span style={{ display: 'flex', gap: 'var(--space-1)' }}>
                      <Button variant="ghost" size="sm" onClick={() => setConfirm(null)}>Cancel</Button>
                      <Button variant="secondary" size="sm" loading={busy} onClick={() => remove(a.ulid)}>Confirm delete</Button>
                    </span>
                  ) : (
                    <Button variant="ghost" size="sm" onClick={() => setConfirm(a.ulid)}>Delete</Button>
                  )}
                </li>
              ))}
            </ul>
          )}

      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </Card>
  );
}

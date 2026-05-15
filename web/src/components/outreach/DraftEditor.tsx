import { useEffect, useMemo, useRef, useState } from 'react';
import { apiGet, apiPatch, apiPost, ApiError } from '../../lib/api';
import type {
  DraftStatus, OutreachChannel, OutreachDraftRecord, OutreachDraftVersionRecord, TemplateRecord,
} from '../../lib/types';
import Dialog from '../ui/Dialog';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import Button from '../ui/Button';
import SendDraftModal from './SendDraftModal';
import './DraftEditor.css';

export interface DraftEditorProps {
  partnerUlid: string;
  draftUlid: string | null;  // null = create new
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

interface FormState {
  channel: OutreachChannel;
  subject: string;
  body: string;
  template_ulid: string;
  status: DraftStatus;
}

const EMPTY: FormState = { channel: 'email', subject: '', body: '', template_ulid: '', status: 'draft' };

export default function DraftEditor({ partnerUlid, draftUlid, isOpen, onClose, onSaved }: DraftEditorProps) {
  const [form, setForm] = useState<FormState>(EMPTY);
  const original = useRef<FormState>(EMPTY);
  const [draftUlidState, setDraftUlidState] = useState<string | null>(draftUlid);
  const [version, setVersion] = useState<number>(1);
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [versions, setVersions] = useState<OutreachDraftVersionRecord[]>([]);
  const [showVersions, setShowVersions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sendOpen, setSendOpen] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Load templates + (optionally) existing draft on open.
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    (async () => {
      setError(null);
      try {
        const tmpls = await apiGet<TemplateRecord[]>('/api/v1/templates');
        if (!cancelled) setTemplates(tmpls);
      } catch (e) { /* templates are optional */ }
      if (draftUlid) {
        try {
          const d = await apiGet<OutreachDraftRecord>(`/api/v1/outreach/drafts/${draftUlid}`);
          if (cancelled) return;
          const next: FormState = {
            channel: d.channel,
            subject: d.subject ?? '',
            body: d.body,
            template_ulid: '',
            status: d.status,
          };
          setForm(next);
          original.current = next;
          setDraftUlidState(d.ulid);
          setVersion(d.version);
          const vs = await apiGet<OutreachDraftVersionRecord[]>(`/api/v1/outreach/drafts/${d.ulid}/versions`);
          if (!cancelled) setVersions(vs);
        } catch (e) {
          if (!cancelled) setError(e instanceof ApiError ? e.message : 'Could not load draft.');
        }
      } else {
        setForm(EMPTY);
        original.current = EMPTY;
        setDraftUlidState(null);
        setVersion(1);
        setVersions([]);
      }
    })();
    return () => { cancelled = true; };
  }, [isOpen, draftUlid]);

  const changedFields = useMemo(() => {
    const o = original.current;
    const ch: Record<string, unknown> = {};
    if (form.channel !== o.channel) ch.channel = form.channel;
    if ((form.subject || '') !== (o.subject || '')) ch.subject = form.subject || null;
    if ((form.body || '') !== (o.body || '')) ch.body = form.body;
    if (form.status !== o.status) ch.status = form.status;
    return ch;
  }, [form]);
  const isDirty = Object.keys(changedFields).length > 0;
  const canSubmit = isDirty && form.body.trim().length > 0 && !submitting;

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
    setError(null);
  }

  async function generateFromTemplate() {
    if (!form.template_ulid) return;
    setGenerating(true);
    setError(null);
    try {
      const rendered = await apiPost<{ subject: string; body: string; missing_variables: string[] }>(
        `/api/v1/templates/${form.template_ulid}/render`,
        { partner_ulid: partnerUlid },
      );
      setForm(prev => ({
        ...prev,
        subject: rendered.subject || prev.subject,
        body: rendered.body || prev.body,
      }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Render failed.');
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    if (!canSubmit && !draftUlidState) return;
    setSubmitting(true);
    setError(null);
    try {
      if (draftUlidState) {
        const updated = await apiPatch<OutreachDraftRecord>(
          `/api/v1/outreach/drafts/${draftUlidState}`,
          changedFields,
        );
        setVersion(updated.version);
        original.current = { ...form };
      } else {
        const idem = `draft-${partnerUlid}-${Date.now()}`;
        const created = await apiPost<OutreachDraftRecord>(
          '/api/v1/outreach/drafts',
          {
            partner_ulid: partnerUlid,
            channel: form.channel,
            subject: form.subject || null,
            body: form.body,
            status: form.status,
          },
          idem,
        );
        setDraftUlidState(created.ulid);
        setVersion(created.version);
        original.current = { ...form };
      }
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Save failed.');
    } finally {
      setSubmitting(false);
    }
  }

  function handleSendClick() {
    if (!draftUlidState) return;
    setSendOpen(true);
  }

  return (
    <>
      <Dialog
        open={isOpen}
        onClose={onClose}
        className="draft-editor-dialog"
        title={draftUlidState ? `Edit draft (v${version})` : 'New draft'}
        children={
          <div className="draft-editor__body">
            <div className="draft-editor__row">
              <Select
                label="Channel"
                name="channel"
                value={form.channel}
                onChange={(e) => set('channel', e.target.value as OutreachChannel)}
              >
                <option value="email">Email</option>
                <option value="linkedin">LinkedIn</option>
                <option value="message">Message</option>
                <option value="other">Other</option>
              </Select>
              <Select
                label="Status"
                name="status"
                value={form.status}
                onChange={(e) => set('status', e.target.value as DraftStatus)}
              >
                <option value="draft">Draft</option>
                <option value="ready">Ready</option>
              </Select>
            </div>

            <div className="draft-editor__template-row">
              <Select
                label="Template"
                name="template"
                value={form.template_ulid}
                onChange={(e) => set('template_ulid', e.target.value)}
              >
                <option value="">— none —</option>
                {templates.map(t => (
                  <option key={t.ulid} value={t.ulid}>{t.name} ({t.channel})</option>
                ))}
              </Select>
              <Button
                variant="secondary"
                size="sm"
                type="button"
                onClick={generateFromTemplate}
                disabled={!form.template_ulid || generating}
                loading={generating}
              >
                Render
              </Button>
            </div>

            <Input
              label="Subject"
              name="subject"
              value={form.subject}
              onChange={(e) => set('subject', e.target.value)}
            />
            <Textarea
              label="Body"
              name="body"
              rows={14}
              value={form.body}
              onChange={(e) => set('body', e.target.value)}
            />

            {versions.length > 0 && (
              <details
                className="draft-editor__history"
                open={showVersions}
                onToggle={(e) => setShowVersions((e.target as HTMLDetailsElement).open)}
              >
                <summary>Version history ({versions.length})</summary>
                <ul className="draft-editor__history-list">
                  {versions.map(v => (
                    <li key={v.ulid} className="draft-editor__history-row">
                      <span className="draft-editor__history-version">v{v.version}</span>
                      <span className="draft-editor__history-actor">{v.author_actor}</span>
                      <span className="draft-editor__history-time">
                        {new Date(v.created_at).toLocaleString()}
                      </span>
                      <details className="draft-editor__history-preview">
                        <summary>peek</summary>
                        <pre>{v.body}</pre>
                      </details>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {error && <div className="draft-editor__error" role="alert">{error}</div>}
          </div>
        }
        footer={
          <>
            <Button variant="ghost" type="button" onClick={onClose} disabled={submitting}>Close</Button>
            <Button
              variant="secondary"
              type="button"
              onClick={handleSave}
              disabled={!canSubmit && !draftUlidState}
              loading={submitting}
            >
              {draftUlidState ? 'Save' : 'Create draft'}
            </Button>
            <Button
              variant="primary"
              type="button"
              onClick={handleSendClick}
              disabled={!draftUlidState || form.status === 'sent' || (form.status as string) === 'archived'}
            >
              Mark sent…
            </Button>
          </>
        }
      />

      {draftUlidState && (
        <SendDraftModal
          draftUlid={draftUlidState}
          defaultChannel={form.channel}
          defaultBody={form.body}
          isOpen={sendOpen}
          onClose={() => setSendOpen(false)}
          onSent={() => { setSendOpen(false); onSaved(); onClose(); }}
        />
      )}
    </>
  );
}

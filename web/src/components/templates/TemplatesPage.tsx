import { useState } from 'react';
import { useFetch } from '../../lib/useFetch';
import { apiPost, apiPatch, apiDelete, ApiError } from '../../lib/api';
import type { OutreachChannel, Partner, TemplateRecord } from '../../lib/types';
import Skeleton from '../ui/Skeleton';
import EmptyState from '../ui/EmptyState';
import Dialog from '../ui/Dialog';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import Button from '../ui/Button';
import './TemplatesPage.css';

interface FormState {
  name: string;
  category: string;
  channel: OutreachChannel;
  subject_template: string;
  body_template: string;
  description: string;
}
const EMPTY: FormState = {
  name: '', category: '', channel: 'email',
  subject_template: '', body_template: '', description: '',
};

export default function TemplatesPage() {
  const templates = useFetch<TemplateRecord[]>('/api/v1/templates');
  const partners = useFetch<Partner[]>('/api/v1/partners');

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<TemplateRecord | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [previewPartnerUlid, setPreviewPartnerUlid] = useState<string>('');
  const [preview, setPreview] = useState<{ subject: string; body: string; missing_variables: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setPreview(null);
    setError(null);
    setEditorOpen(true);
  }
  function openExisting(t: TemplateRecord) {
    setEditing(t);
    setForm({
      name: t.name,
      category: t.category ?? '',
      channel: t.channel,
      subject_template: t.subject_template ?? '',
      body_template: t.body_template,
      description: t.description ?? '',
    });
    setPreview(null);
    setError(null);
    setEditorOpen(true);
  }

  async function handleSave() {
    setSubmitting(true);
    setError(null);
    try {
      if (editing) {
        await apiPatch(`/api/v1/templates/${editing.ulid}`, {
          name: form.name,
          category: form.category || null,
          channel: form.channel,
          subject_template: form.subject_template || null,
          body_template: form.body_template,
          description: form.description || null,
        });
      } else {
        await apiPost('/api/v1/templates', {
          name: form.name,
          category: form.category || null,
          channel: form.channel,
          subject_template: form.subject_template || null,
          body_template: form.body_template,
          description: form.description || null,
        });
      }
      setEditorOpen(false);
      templates.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Save failed.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!editing) return;
    if (!confirm(`Delete template "${editing.name}"?`)) return;
    try {
      await apiDelete(`/api/v1/templates/${editing.ulid}`);
      setEditorOpen(false);
      templates.refresh();
    } catch (e) { /* ignore */ }
  }

  async function runPreview() {
    if (!editing || !previewPartnerUlid) return;
    setError(null);
    try {
      const r = await apiPost<{ subject: string; body: string; missing_variables: string[] }>(
        `/api/v1/templates/${editing.ulid}/render`,
        { partner_ulid: previewPartnerUlid },
      );
      setPreview(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Render failed.');
    }
  }

  return (
    <div className="templates-page">
      <div className="templates-page__toolbar">
        <Button variant="primary" onClick={openNew}>+ New template</Button>
      </div>

      {templates.loading && <Skeleton width="100%" height={120} />}
      {templates.data && templates.data.length === 0 && (
        <EmptyState title="No templates yet" description="Create one to standardise your outreach scaffolds." />
      )}
      {templates.data && templates.data.length > 0 && (
        <ul className="templates-list">
          {templates.data.map(t => (
            <li key={t.ulid}>
              <button type="button" className="templates-list__row" onClick={() => openExisting(t)}>
                <span className="templates-list__name">{t.name}</span>
                <span className="templates-list__channel">{t.channel}</span>
                <span className="templates-list__category">{t.category ?? '—'}</span>
                <span className="templates-list__desc">{t.description?.slice(0, 80) ?? ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <Dialog
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        className="template-editor-dialog"
        title={editing ? `Edit: ${editing.name}` : 'New template'}
        children={
          <div className="template-editor">
            <div className="template-editor__form">
              <Input
                label="Name"
                name="name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <div className="template-editor__row">
                <Select
                  label="Channel"
                  value={form.channel}
                  onChange={(e) => setForm({ ...form, channel: e.target.value as OutreachChannel })}
                >
                  <option value="email">Email</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="message">Message</option>
                  <option value="other">Other</option>
                </Select>
                <Input
                  label="Category"
                  name="category"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                />
              </div>
              <Input
                label="Subject template"
                name="subject_template"
                value={form.subject_template}
                onChange={(e) => setForm({ ...form, subject_template: e.target.value })}
              />
              <Textarea
                label="Body template"
                name="body_template"
                rows={10}
                value={form.body_template}
                onChange={(e) => setForm({ ...form, body_template: e.target.value })}
              />
              <Textarea
                label="Description (internal note)"
                name="description"
                rows={2}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
              {error && <div className="template-editor__error">{error}</div>}
            </div>

            <div className="template-editor__preview">
              <h3>Live preview</h3>
              <Select
                label="Preview against partner"
                value={previewPartnerUlid}
                onChange={(e) => setPreviewPartnerUlid(e.currentTarget.value)}
                disabled={!editing}
              >
                <option value="">— pick partner —</option>
                {(partners.data ?? []).map(p => (
                  <option key={p.ulid} value={p.ulid}>{p.name}</option>
                ))}
              </Select>
              <Button
                variant="secondary"
                size="sm"
                onClick={runPreview}
                disabled={!editing || !previewPartnerUlid}
              >
                Render
              </Button>
              {!editing && (
                <p className="template-editor__hint">
                  Save the template first to preview it.
                </p>
              )}
              {preview && (
                <div className="template-editor__preview-output">
                  <div className="template-editor__preview-subject">
                    <strong>Subject:</strong> {preview.subject}
                  </div>
                  <pre className="template-editor__preview-body">{preview.body}</pre>
                  {preview.missing_variables.length > 0 && (
                    <div className="template-editor__preview-missing">
                      Missing: {preview.missing_variables.join(', ')}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        }
        footer={
          <>
            {editing && (
              <Button variant="ghost" onClick={handleDelete}>Delete</Button>
            )}
            <Button variant="ghost" onClick={() => setEditorOpen(false)}>Close</Button>
            <Button variant="primary" onClick={handleSave} loading={submitting}>
              {editing ? 'Save' : 'Create'}
            </Button>
          </>
        }
      />
    </div>
  );
}

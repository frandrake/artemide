import { useEffect, useMemo, useRef, useState } from 'react';
import { apiPatch, ApiError } from '../../lib/api';
import type { Partner } from '../../lib/types';
import Dialog from '../ui/Dialog';
import Input from '../ui/Input';
import Button from '../ui/Button';
import './EditPartnerModal.css';

export interface EditPartnerModalProps {
  partner: Partner;
  firmName: string;
  isOpen: boolean;
  onClose: () => void;
  onSaved: (updated: Partner) => void;
  onDeleteRequest: () => void;
}

function parseFollowUps(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch { return []; }
}

interface FormState {
  name: string;
  practice: string;
  seniority: string;
  location: string;
  introduced_via: string;
  first_contact_date: string;
  next_planned_touch_date: string;
  next_planned_topic: string;
}

function fromPartner(p: Partner): FormState {
  return {
    name: p.name,
    practice: p.practice ?? '',
    seniority: p.seniority ?? '',
    location: p.location ?? '',
    introduced_via: p.introduced_via ?? '',
    first_contact_date: p.last_contact_date ?? '',
    next_planned_touch_date: p.next_touch_date ?? '',
    next_planned_topic: p.next_touch_topic ?? '',
  };
}

export function EditPartnerModal({ partner, firmName, isOpen, onClose, onSaved, onDeleteRequest }: EditPartnerModalProps) {
  const original = useRef<FormState>(fromPartner(partner));
  const originalFollowUps = useRef<string[]>(parseFollowUps(partner.follow_ups_outstanding));

  const [form, setForm] = useState<FormState>(() => fromPartner(partner));
  const [followUps, setFollowUps] = useState<string[]>(() => parseFollowUps(partner.follow_ups_outstanding));
  const [followUpDraft, setFollowUpDraft] = useState('');
  const [followUpsTouched, setFollowUpsTouched] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dangerOpen, setDangerOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const init = fromPartner(partner);
      const initFu = parseFollowUps(partner.follow_ups_outstanding);
      original.current = init;
      originalFollowUps.current = initFu;
      setForm(init);
      setFollowUps(initFu);
      setFollowUpDraft('');
      setFollowUpsTouched(false);
      setError(null);
      setDangerOpen(false);
    }
  }, [isOpen, partner]);

  const changedFields = useMemo(() => {
    const o = original.current;
    const changes: Record<string, unknown> = {};
    if (form.name !== o.name) changes.name = form.name;
    if ((form.practice || '') !== (o.practice || '')) changes.practice = form.practice || null;
    if ((form.seniority || '') !== (o.seniority || '')) changes.seniority = form.seniority || null;
    if ((form.location || '') !== (o.location || '')) changes.location = form.location || null;
    if ((form.introduced_via || '') !== (o.introduced_via || '')) changes.introduced_via = form.introduced_via || null;
    if ((form.first_contact_date || '') !== (o.first_contact_date || '')) changes.first_contact_date = form.first_contact_date || null;
    if ((form.next_planned_touch_date || '') !== (o.next_planned_touch_date || '')) changes.next_planned_touch_date = form.next_planned_touch_date || null;
    if ((form.next_planned_topic || '') !== (o.next_planned_topic || '')) changes.next_planned_topic = form.next_planned_topic || null;
    if (followUpsTouched) changes.follow_ups_outstanding = followUps;
    return changes;
  }, [form, followUps, followUpsTouched]);

  const isDirty = Object.keys(changedFields).length > 0;
  const nameChanged = form.name !== original.current.name;
  const nameInvalid = !form.name.trim();
  const canSubmit = isDirty && !nameInvalid && !submitting;

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setError(null);
  }

  function addFollowUp() {
    const trimmed = followUpDraft.trim();
    if (!trimmed) return;
    setFollowUps((prev) => [...prev, trimmed]);
    setFollowUpDraft('');
    setFollowUpsTouched(true);
  }

  function removeFollowUp(i: number) {
    setFollowUps((prev) => prev.filter((_, idx) => idx !== i));
    setFollowUpsTouched(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await apiPatch<Partner>(`/api/v1/partners/${partner.ulid}`, changedFields);
      onSaved(updated);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message || 'Save failed.');
      } else {
        setError('Save failed.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleDeleteRequest() {
    onClose();
    onDeleteRequest();
  }

  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      ariaLabel={`Edit ${partner.name}`}
      className="edit-partner-dialog"
      title="Edit partner"
      children={
        <form id="edit-partner-form" onSubmit={handleSubmit} className="edit-partner-modal__form">
          {/* Name */}
          <div className="edit-partner-modal__field">
            <Input
              label="Name"
              name="name"
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
            />
            {nameInvalid && (
              <div className="edit-partner-modal__error" role="alert">
                Name is required.
              </div>
            )}
            {nameChanged && !nameInvalid && (
              <div className="edit-partner-modal__name-warning">
                Renaming this partner may break voice lookups. Update any Claude references to their name.
              </div>
            )}
          </div>

          {/* Firm (read-only) */}
          <div className="edit-partner-modal__field">
            <span className="edit-partner-modal__field-label">Firm</span>
            <div className="edit-partner-modal__firm-readonly">{firmName}</div>
            <span className="edit-partner-modal__firm-note">
              To reassign, create a new partner record at the target firm.
            </span>
          </div>

          <Input
            label="Practice"
            name="practice"
            value={form.practice}
            onChange={(e) => set('practice', e.target.value)}
          />

          <Input
            label="Seniority"
            name="seniority"
            value={form.seniority}
            onChange={(e) => set('seniority', e.target.value)}
          />

          <Input
            label="Location"
            name="location"
            value={form.location}
            onChange={(e) => set('location', e.target.value)}
          />

          <Input
            label="Introduced via"
            name="introduced_via"
            value={form.introduced_via}
            onChange={(e) => set('introduced_via', e.target.value)}
          />

          <Input
            label="First contact date"
            name="first_contact_date"
            type="date"
            value={form.first_contact_date}
            onChange={(e) => set('first_contact_date', e.target.value)}
          />

          <Input
            label="Next planned touch"
            name="next_planned_touch_date"
            type="date"
            value={form.next_planned_touch_date}
            onChange={(e) => set('next_planned_touch_date', e.target.value)}
          />

          <Input
            label="Next planned topic"
            name="next_planned_topic"
            value={form.next_planned_topic}
            onChange={(e) => set('next_planned_topic', e.target.value)}
          />

          {/* Follow-ups tag editor */}
          <div className="edit-partner-modal__field">
            <span className="edit-partner-modal__field-label">Follow-ups</span>
            <div className="edit-partner-modal__pills">
              {followUps.map((item, i) => (
                <span key={i} className="edit-partner-modal__pill">
                  {item}
                  <button
                    type="button"
                    className="edit-partner-modal__pill-remove"
                    aria-label={`Remove follow-up: ${item}`}
                    onClick={() => removeFollowUp(i)}
                  >×</button>
                </span>
              ))}
            </div>
            <div className="edit-partner-modal__follow-up-add">
              <input
                type="text"
                className="edit-partner-modal__follow-up-input"
                placeholder="Add a follow-up…"
                value={followUpDraft}
                onChange={(e) => setFollowUpDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addFollowUp(); } }}
              />
              <Button
                variant="secondary"
                size="sm"
                type="button"
                onClick={addFollowUp}
                disabled={!followUpDraft.trim()}
              >
                Add
              </Button>
            </div>
          </div>

          {error && (
            <div className="edit-partner-modal__error" role="alert">
              {error}
            </div>
          )}

          {/* Danger zone */}
          <div className="edit-partner-modal__danger-zone">
            <button
              type="button"
              className="edit-partner-modal__danger-toggle"
              onClick={() => setDangerOpen((v) => !v)}
              aria-expanded={dangerOpen}
            >
              Danger zone
              <span className={`edit-partner-modal__chevron${dangerOpen ? ' is-open' : ''}`} aria-hidden="true">▾</span>
            </button>
            {dangerOpen && (
              <div className="edit-partner-modal__danger-body">
                <button
                  type="button"
                  className="edit-partner-modal__delete-btn"
                  onClick={handleDeleteRequest}
                >
                  Delete partner
                </button>
              </div>
            )}
          </div>
        </form>
      }
      footer={
        <>
          <Button variant="ghost" type="button" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            form="edit-partner-form"
            disabled={!canSubmit}
            loading={submitting}
          >
            Save changes
          </Button>
        </>
      }
    />
  );
}

export default EditPartnerModal;

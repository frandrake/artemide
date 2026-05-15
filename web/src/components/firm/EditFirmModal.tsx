import { useEffect, useMemo, useRef, useState } from 'react';
import { apiPatch, ApiError } from '../../lib/api';
import type { Firm, FirmTier, RelationshipState } from '../../lib/types';
import Dialog from '../ui/Dialog';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import Button from '../ui/Button';
import './EditFirmModal.css';

export interface EditFirmModalProps {
  firm: Firm;
  isOpen: boolean;
  onClose: () => void;
  onSaved: (updated: Firm) => void;
  onDeleteRequest: () => void;
}

interface FormState {
  tier: FirmTier;
  region: string;
  relationship_state: RelationshipState;
  notes: string;
}

function fromFirm(firm: Firm): FormState {
  return {
    tier: firm.tier,
    region: firm.region ?? '',
    relationship_state: firm.relationship_state,
    notes: firm.notes_summary ?? '',
  };
}

export function EditFirmModal({ firm, isOpen, onClose, onSaved, onDeleteRequest }: EditFirmModalProps) {
  const original = useRef<FormState>(fromFirm(firm));
  const [form, setForm] = useState<FormState>(() => fromFirm(firm));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dangerOpen, setDangerOpen] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const init = fromFirm(firm);
      original.current = init;
      setForm(init);
      setError(null);
      setDangerOpen(false);
    }
  }, [isOpen, firm]);

  const changedFields = useMemo(() => {
    const o = original.current;
    const changes: Record<string, unknown> = {};
    if (form.tier !== o.tier) changes.tier = form.tier;
    if ((form.region || '') !== (o.region || '')) changes.region = form.region || null;
    if (form.relationship_state !== o.relationship_state) changes.relationship_state = form.relationship_state;
    if ((form.notes || '') !== (o.notes || '')) changes.notes = form.notes || null;
    return changes;
  }, [form]);

  const isDirty = Object.keys(changedFields).length > 0;

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isDirty || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await apiPatch<Firm>(`/api/v1/firms/${firm.ulid}`, changedFields);
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
      ariaLabel={`Edit ${firm.name}`}
      title={
        <span className="edit-firm-modal__heading">
          {firm.name}
          <span className="edit-firm-modal__name-note">Firm name cannot be changed.</span>
        </span>
      }
      children={
        <form id="edit-firm-form" onSubmit={handleSubmit} className="edit-firm-modal__form">
          <Select
            label="Tier"
            name="tier"
            value={form.tier}
            onChange={(e) => set('tier', e.target.value as FirmTier)}
          >
            <option value="primary">Primary</option>
            <option value="specialist">Specialist</option>
            <option value="ned">NED</option>
          </Select>

          <Input
            label="Region"
            name="region"
            value={form.region}
            onChange={(e) => set('region', e.target.value)}
          />

          <Select
            label="Relationship state"
            name="relationship_state"
            value={form.relationship_state}
            onChange={(e) => set('relationship_state', e.target.value as RelationshipState)}
          >
            <option value="cold">Cold</option>
            <option value="warming">Warming</option>
            <option value="warm">Warm</option>
            <option value="dormant">Dormant</option>
          </Select>

          <Textarea
            label="Notes"
            name="notes"
            rows={5}
            value={form.notes}
            onChange={(e) => set('notes', e.target.value)}
          />

          {error && (
            <div className="edit-firm-modal__error" role="alert">
              {error}
            </div>
          )}

          <div className="edit-firm-modal__danger-zone">
            <button
              type="button"
              className="edit-firm-modal__danger-toggle"
              onClick={() => setDangerOpen((v) => !v)}
              aria-expanded={dangerOpen}
            >
              Danger zone
              <span className={`edit-firm-modal__chevron${dangerOpen ? ' is-open' : ''}`} aria-hidden="true">▾</span>
            </button>
            {dangerOpen && (
              <div className="edit-firm-modal__danger-body">
                <button
                  type="button"
                  className="edit-firm-modal__delete-btn"
                  onClick={handleDeleteRequest}
                >
                  Delete firm
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
            form="edit-firm-form"
            disabled={!isDirty || submitting}
            loading={submitting}
          >
            Save changes
          </Button>
        </>
      }
    />
  );
}

export default EditFirmModal;

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
  market_tier: string;
  strategic_fit: string;
  ned_practice_strength: string;
  hq_address: string;
  sectors: string;
  cmo_practice_depth: string;
  comp_transparency: string;
  candidate_reputation: string;
  b2b_fs_reputation: string;
}

function fromFirm(firm: Firm): FormState {
  return {
    tier: firm.tier,
    region: firm.region ?? '',
    relationship_state: firm.relationship_state,
    notes: firm.notes_summary ?? '',
    market_tier: firm.market_tier ?? '',
    strategic_fit: firm.strategic_fit ?? '',
    ned_practice_strength: firm.ned_practice_strength ?? '',
    hq_address: firm.hq_address ?? '',
    sectors: firm.sectors ?? '',
    cmo_practice_depth: firm.cmo_practice_depth ?? '',
    comp_transparency: firm.comp_transparency ?? '',
    candidate_reputation: firm.candidate_reputation ?? '',
    b2b_fs_reputation: firm.b2b_fs_reputation ?? '',
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
    const intelFields: (keyof FormState)[] = [
      'market_tier', 'strategic_fit', 'ned_practice_strength', 'hq_address',
      'sectors', 'cmo_practice_depth', 'comp_transparency',
      'candidate_reputation', 'b2b_fs_reputation',
    ];
    for (const k of intelFields) {
      if ((form[k] || '') !== (o[k] || '')) {
        changes[k] = form[k] || null;
      }
    }
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
            {form.tier === 'ned' && <option value="ned" disabled>Legacy board-practice tier — reclassify</option>}
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

          <details className="edit-firm-modal__intel-section">
            <summary>Headhunter intelligence</summary>
            <div className="edit-firm-modal__intel-grid">
              <Select
                label="Market tier"
                name="market_tier"
                value={form.market_tier}
                onChange={(e) => set('market_tier', e.target.value)}
              >
                <option value="">—</option>
                <option value="tier-1-global">Tier-1 global</option>
                <option value="specialist-boutique">Specialist boutique</option>
                <option value="honourable-mention">Honourable mention</option>
              </Select>
              <Select
                label="Strategic fit"
                name="strategic_fit"
                value={form.strategic_fit}
                onChange={(e) => set('strategic_fit', e.target.value)}
              >
                <option value="">—</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </Select>
              <Select
                label="NED practice strength"
                name="ned_practice_strength"
                value={form.ned_practice_strength}
                onChange={(e) => set('ned_practice_strength', e.target.value)}
              >
                <option value="">—</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
                <option value="N/A">N/A</option>
              </Select>
              <Input
                label="HQ address"
                name="hq_address"
                value={form.hq_address}
                onChange={(e) => set('hq_address', e.target.value)}
              />
              <Input
                label="Sectors (comma-separated)"
                name="sectors"
                value={form.sectors}
                onChange={(e) => set('sectors', e.target.value)}
              />
              <Textarea
                label="CMO practice depth"
                name="cmo_practice_depth"
                rows={3}
                value={form.cmo_practice_depth}
                onChange={(e) => set('cmo_practice_depth', e.target.value)}
              />
              <Textarea
                label="Comp transparency"
                name="comp_transparency"
                rows={2}
                value={form.comp_transparency}
                onChange={(e) => set('comp_transparency', e.target.value)}
              />
              <Textarea
                label="Candidate reputation"
                name="candidate_reputation"
                rows={2}
                value={form.candidate_reputation}
                onChange={(e) => set('candidate_reputation', e.target.value)}
              />
              <Textarea
                label="B2B / FS reputation"
                name="b2b_fs_reputation"
                rows={2}
                value={form.b2b_fs_reputation}
                onChange={(e) => set('b2b_fs_reputation', e.target.value)}
              />
            </div>
          </details>

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

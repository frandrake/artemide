import { useState, type FormEvent } from 'react';
import { apiPatch } from '../../lib/api';
import type {
  BoardAppointmentCategory,
  BoardDoInsuranceStatus,
  BoardFiduciaryStatus,
  BoardOpportunity,
} from '../../lib/types';
import { titleCase } from './helpers';

const CATEGORIES: BoardAppointmentCategory[] = [
  'ned_unspecified', 'independent_ned', 'non_independent_ned', 'board_chair',
  'senior_independent_director', 'committee_chair', 'committee_member', 'trustee',
  'advisory_board', 'editorial_board', 'other_board',
];
const FIDUCIARY: BoardFiduciaryStatus[] = [
  'requires_confirmation', 'statutory_fiduciary', 'contractual_non_fiduciary',
];
const DO_STATUS: BoardDoInsuranceStatus[] = ['pending', 'confirmed', 'not_confirmed'];
const ADVISORY = new Set<BoardAppointmentCategory>(['advisory_board', 'editorial_board']);

interface Props {
  opportunity: BoardOpportunity;
  onSaved: () => Promise<void> | void;
}

function show(value: string | number | null) {
  return value === null || value === '' ? '—' : String(value);
}

export default function BoardGovernanceProfile({ opportunity: o, onSaved }: Props) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<BoardAppointmentCategory | ''>(o.appointment_category ?? '');
  const [fiduciary, setFiduciary] = useState<BoardFiduciaryStatus>(o.fiduciary_status);
  const [legalEntity, setLegalEntity] = useState(o.legal_entity ?? '');
  const [days, setDays] = useState(o.time_commitment_days?.toString() ?? '');
  const [term, setTerm] = useState(o.term_length_months?.toString() ?? '');
  const [fee, setFee] = useState(o.annual_fee_gbp?.toString() ?? '');
  const [committees, setCommittees] = useState(o.committee_expectations ?? '');
  const [independence, setIndependence] = useState(o.independence_requirement ?? '');
  const [indemnity, setIndemnity] = useState(o.liability_indemnity_notes ?? '');
  const [doStatus, setDoStatus] = useState<BoardDoInsuranceStatus>(o.do_insurance_status);
  const [conflicts, setConflicts] = useState(o.conflicts_notes ?? '');
  const [dueDiligence, setDueDiligence] = useState(o.due_diligence_notes ?? '');
  const [nextDue, setNextDue] = useState(o.next_step_due_date ?? '');

  function changeCategory(value: BoardAppointmentCategory | '') {
    setCategory(value);
    if (value && ADVISORY.has(value)) setFiduciary('contractual_non_fiduciary');
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await apiPatch(`/api/v1/board/opportunities/${o.ulid}`, {
        ...(category ? { appointment_category: category } : {}),
        fiduciary_status: fiduciary,
        legal_entity: legalEntity || null,
        time_commitment_days: days ? Number(days) : null,
        term_length_months: term ? Number(term) : null,
        annual_fee_gbp: fee ? Number(fee) : null,
        committee_expectations: committees || null,
        independence_requirement: independence || null,
        liability_indemnity_notes: indemnity || null,
        do_insurance_status: doStatus,
        conflicts_notes: conflicts || null,
        due_diligence_notes: dueDiligence || null,
        next_step_due_date: nextDue || null,
      });
      setEditing(false);
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save governance profile.');
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <>
        {o.fiduciary_status === 'requires_confirmation' && (
          <p className="bd-warning"><strong>Classification required:</strong> confirm whether this appointment carries statutory or contractual fiduciary duties before external use.</p>
        )}
        <dl className="bd-kv">
          <dt>Appointment</dt><dd>{o.appointment_category ? titleCase(o.appointment_category) : 'Unclassified'}</dd>
          <dt>Legal status</dt><dd>{titleCase(o.fiduciary_status)}</dd>
          <dt>Legal entity</dt><dd>{show(o.legal_entity)}</dd>
          <dt>Time commitment</dt><dd>{o.time_commitment_days == null ? '—' : `${o.time_commitment_days} days/year`}</dd>
          <dt>Term</dt><dd>{o.term_length_months == null ? '—' : `${o.term_length_months} months`}</dd>
          <dt>Annual fee</dt><dd>{o.annual_fee_gbp == null ? '—' : `£${o.annual_fee_gbp.toLocaleString('en-GB')}`}</dd>
          <dt>Committees</dt><dd>{show(o.committee_expectations)}</dd>
          <dt>Independence</dt><dd>{show(o.independence_requirement)}</dd>
          <dt>Indemnity</dt><dd>{show(o.liability_indemnity_notes)}</dd>
          <dt>D&amp;O insurance</dt><dd>{titleCase(o.do_insurance_status)}</dd>
          <dt>Conflicts</dt><dd>{show(o.conflicts_notes)}</dd>
          <dt>Due diligence</dt><dd>{show(o.due_diligence_notes)}</dd>
          <dt>Next-step due</dt><dd>{show(o.next_step_due_date)}</dd>
        </dl>
        <button type="button" className="bd-btn bd-btn--ghost" onClick={() => setEditing(true)}>Edit governance profile</button>
      </>
    );
  }

  return (
    <form onSubmit={save} className="bd-governance-form">
      <div className="bd-form-grid">
        <label className="bd-field"><span>Appointment category</span>
          <select value={category} onChange={(e) => changeCategory(e.currentTarget.value as BoardAppointmentCategory | '')}>
            <option value="">Unclassified</option>
            {CATEGORIES.map((v) => <option key={v} value={v}>{titleCase(v)}</option>)}
          </select>
        </label>
        <label className="bd-field"><span>Fiduciary status</span>
          <select value={fiduciary} onChange={(e) => setFiduciary(e.currentTarget.value as BoardFiduciaryStatus)}>
            {FIDUCIARY.map((v) => <option key={v} value={v} disabled={Boolean(category && ADVISORY.has(category) && v !== 'contractual_non_fiduciary')}>{titleCase(v)}</option>)}
          </select>
        </label>
        <label className="bd-field"><span>Legal entity</span><input value={legalEntity} onChange={(e) => setLegalEntity(e.currentTarget.value)} /></label>
        <label className="bd-field"><span>Time commitment (days/year)</span><input type="number" min="0" value={days} onChange={(e) => setDays(e.currentTarget.value)} /></label>
        <label className="bd-field"><span>Term (months)</span><input type="number" min="1" value={term} onChange={(e) => setTerm(e.currentTarget.value)} /></label>
        <label className="bd-field"><span>Annual fee (£)</span><input type="number" min="0" value={fee} onChange={(e) => setFee(e.currentTarget.value)} /></label>
        <label className="bd-field"><span>D&amp;O insurance</span><select value={doStatus} onChange={(e) => setDoStatus(e.currentTarget.value as BoardDoInsuranceStatus)}>{DO_STATUS.map((v) => <option key={v} value={v}>{titleCase(v)}</option>)}</select></label>
        <label className="bd-field"><span>Next-step due</span><input type="date" value={nextDue} onChange={(e) => setNextDue(e.currentTarget.value)} /></label>
      </div>
      <label className="bd-field"><span>Committee expectations</span><textarea value={committees} onChange={(e) => setCommittees(e.currentTarget.value)} /></label>
      <label className="bd-field"><span>Independence requirement</span><textarea value={independence} onChange={(e) => setIndependence(e.currentTarget.value)} /></label>
      <label className="bd-field"><span>Liability and indemnity</span><textarea value={indemnity} onChange={(e) => setIndemnity(e.currentTarget.value)} /></label>
      <label className="bd-field"><span>Potential conflicts</span><textarea value={conflicts} onChange={(e) => setConflicts(e.currentTarget.value)} /></label>
      <label className="bd-field"><span>Due-diligence findings and unknowns</span><textarea rows={4} value={dueDiligence} onChange={(e) => setDueDiligence(e.currentTarget.value)} /></label>
      <button type="submit" className="bd-btn" disabled={saving}>{saving ? 'Saving…' : 'Save governance profile'}</button>{' '}
      <button type="button" className="bd-btn bd-btn--ghost" onClick={() => setEditing(false)}>Cancel</button>
      {error && <p className="bd-error">{error}</p>}
    </form>
  );
}

import { useState, type FormEvent } from 'react';
import { apiPatch, apiPost, ApiError } from '../../lib/api';
import { useFetch } from '../../lib/useFetch';
import type { CompScenario, CompScenarioStatus, Engagement } from '../../lib/types';
import Button from '../ui/Button';
import Dialog from '../ui/Dialog';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';

const STATUSES: CompScenarioStatus[] = ['current', 'offer', 'negotiating', 'accepted', 'rejected'];

interface Props {
  scenario: CompScenario | null; // null = create
  onClose: () => void;
  onSaved: () => void;
}

interface FormState {
  name: string;
  status: CompScenarioStatus;
  engagement_ulid: string;
  base_gbp: string;
  cash_bonus_gbp: string;
  equity_gbp: string;
  equity_note: string;
  pension_pct: string;
  healthcare_gbp: string;
  car_allowance_gbp: string;
  other_gbp: string;
  benefits_note: string;
}

function toForm(s: CompScenario | null): FormState {
  return {
    name: s?.name ?? '',
    status: s?.status ?? 'offer',
    engagement_ulid: s?.engagement_ulid ?? '',
    base_gbp: s?.base_gbp?.toString() ?? '',
    cash_bonus_gbp: s?.cash_bonus_gbp?.toString() ?? '',
    equity_gbp: s?.equity_gbp?.toString() ?? '',
    equity_note: s?.equity_note ?? '',
    pension_pct: s?.pension_pct?.toString() ?? '',
    healthcare_gbp: s?.healthcare_gbp?.toString() ?? '',
    car_allowance_gbp: s?.car_allowance_gbp?.toString() ?? '',
    other_gbp: s?.other_gbp?.toString() ?? '',
    benefits_note: s?.benefits_note ?? '',
  };
}

const intOrNull = (v: string): number | null => (v.trim() === '' ? null : Math.round(Number(v)));
const floatOrNull = (v: string): number | null => (v.trim() === '' ? null : Number(v));

export function ScenarioForm({ scenario, onClose, onSaved }: Props) {
  const [form, setForm] = useState<FormState>(() => toForm(scenario));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const engagements = useFetch<Engagement[]>('/api/v1/engagements');

  const set = (key: keyof FormState) => (
    e: FormEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => setForm((f) => ({ ...f, [key]: e.currentTarget.value }));

  const numeric = [
    ['base_gbp', 'Base salary (£/yr)'],
    ['cash_bonus_gbp', 'Cash bonus (£/yr)'],
    ['equity_gbp', 'Equity, annualised (£/yr)'],
    ['healthcare_gbp', 'Healthcare (£/yr)'],
    ['car_allowance_gbp', 'Car allowance (£/yr)'],
    ['other_gbp', 'Other (£/yr)'],
  ] as const;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setError('Name is required.'); return; }
    setSaving(true);
    setError(null);
    const body = {
      name: form.name.trim(),
      status: form.status,
      engagement_ulid: form.engagement_ulid || null,
      base_gbp: intOrNull(form.base_gbp),
      cash_bonus_gbp: intOrNull(form.cash_bonus_gbp),
      equity_gbp: intOrNull(form.equity_gbp),
      equity_note: form.equity_note.trim() || null,
      pension_pct: floatOrNull(form.pension_pct),
      healthcare_gbp: intOrNull(form.healthcare_gbp),
      car_allowance_gbp: intOrNull(form.car_allowance_gbp),
      other_gbp: intOrNull(form.other_gbp),
      benefits_note: form.benefits_note.trim() || null,
    };
    try {
      if (scenario) {
        // PATCH so cleared fields are written back as null.
        await apiPatch(`/api/v1/comp-scenarios/${scenario.ulid}`, body);
      } else {
        await apiPost('/api/v1/comp-scenarios', body, crypto.randomUUID());
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Save failed.');
      setSaving(false);
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={scenario ? `Edit · ${scenario.name}` : 'New scenario'}
      className="comp-form-dialog"
    >
      <form onSubmit={submit} className="comp-form">
        <Input label="Name" name="name" value={form.name} onInput={set('name')} required
               placeholder="e.g. Acme CMO — offer v2" />
        <div className="comp-form__row">
          <Select label="Status" name="status" value={form.status} onChange={set('status')}>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
          <Select
            label="Linked engagement"
            name="engagement_ulid"
            value={form.engagement_ulid}
            onChange={set('engagement_ulid')}
            hint={engagements.error ? 'Could not load engagements.' : undefined}
          >
            <option value="">— none —</option>
            {(engagements.data ?? []).map((e) => (
              <option key={e.ulid} value={e.ulid}>
                {e.org_name ? `${e.org_name} — ${e.role_title}` : e.role_title}
              </option>
            ))}
          </Select>
        </div>
        <div className="comp-form__grid">
          {numeric.map(([key, label]) => (
            <Input key={key} label={label} name={key} type="number" min={0} step={1000}
                   value={form[key]} onInput={set(key)} placeholder="—" />
          ))}
          <Input label="Pension (% of base)" name="pension_pct" type="number" min={0} max={100}
                 step={0.5} value={form.pension_pct} onInput={set('pension_pct')} placeholder="—" />
        </div>
        <Textarea label="Equity note" name="equity_note" rows={2} value={form.equity_note}
                  onInput={set('equity_note')} placeholder="Vesting, instrument, refreshers…" />
        <Textarea label="Benefits note" name="benefits_note" rows={2} value={form.benefits_note}
                  onInput={set('benefits_note')} placeholder="Anything not captured above…" />
        {error && <p className="form-message form-message--error" role="alert">{error}</p>}
        <div className="comp-form__actions">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={saving}>{scenario ? 'Save changes' : 'Create scenario'}</Button>
        </div>
      </form>
    </Dialog>
  );
}

export default ScenarioForm;

import { useMemo, useState, type FormEvent } from 'react';
import Button from '../ui/Button';
import Dialog from '../ui/Dialog';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import { apiPost, ApiError } from '../../lib/api';
import type {
  ContactChannel,
  ContactLogResponse,
  InitiatedBy,
} from '../../lib/types';
import { generateUlid } from '../../lib/ulid';
import './LogContactForm.css';

const CHANNELS: ContactChannel[] = [
  'email', 'call', 'coffee', 'event', 'inmail', 'message', 'other',
];

export interface LogContactFormProps {
  open: boolean;
  onClose: () => void;
  firmName: string;
  partnerName: string;
  onLogged?: (resp: ContactLogResponse) => void;
}

export default function LogContactForm({
  open, onClose, firmName, partnerName, onLogged,
}: LogContactFormProps) {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [contactDate, setContactDate] = useState(today);
  const [channel, setChannel] = useState<ContactChannel>('email');
  const [initiatedBy, setInitiatedBy] = useState<InitiatedBy>('me');
  const [summary, setSummary] = useState('');
  const [valueGiven, setValueGiven] = useState('');
  const [valueReceived, setValueReceived] = useState('');
  const [followUp, setFollowUp] = useState('');
  const [advanceState, setAdvanceState] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // One Idempotency-Key per form session, regenerated on reset.
  const [idempotencyKey, setIdempotencyKey] = useState(() => generateUlid());

  function reset() {
    setContactDate(today);
    setChannel('email');
    setInitiatedBy('me');
    setSummary('');
    setValueGiven('');
    setValueReceived('');
    setFollowUp('');
    setAdvanceState(false);
    setError(null);
    setIdempotencyKey(generateUlid());
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const resp = await apiPost<ContactLogResponse>(
        '/api/v1/contacts',
        {
          firm_name: firmName,
          partner_name: partnerName,
          contact_date: contactDate,
          channel,
          initiated_by: initiatedBy,
          summary: summary || null,
          value_given: valueGiven || null,
          value_received: valueReceived || null,
          follow_up: followUp || null,
          advance_state: advanceState,
        },
        idempotencyKey,
      );
      onLogged?.(resp);
      reset();
      onClose();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message :
        e instanceof Error ? e.message :
        'Failed to log contact.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Log contact"
      ariaLabel={`Log a contact with ${partnerName}`}
    >
      <form className="log-contact-form" onSubmit={onSubmit} noValidate>
        <p className="log-contact-form__subject">
          With <strong>{partnerName}</strong> at <strong>{firmName}</strong>
        </p>

        <div className="log-contact-form__row">
          <Input
            label="Date"
            type="date"
            name="contact_date"
            value={contactDate}
            onChange={(e) => setContactDate(e.currentTarget.value)}
            required
          />
          <Select
            label="Channel"
            name="channel"
            value={channel}
            onChange={(e) => setChannel(e.currentTarget.value as ContactChannel)}
          >
            {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
          </Select>
        </div>

        <Select
          label="Initiated by"
          name="initiated_by"
          value={initiatedBy}
          onChange={(e) => setInitiatedBy(e.currentTarget.value as InitiatedBy)}
        >
          <option value="me">FF</option>
          <option value="them">Partner</option>
        </Select>

        <Textarea
          label="Summary"
          name="summary"
          hint="One line."
          rows={2}
          value={summary}
          onChange={(e) => setSummary(e.currentTarget.value)}
        />
        <Textarea
          label="Value given"
          name="value_given"
          rows={2}
          value={valueGiven}
          onChange={(e) => setValueGiven(e.currentTarget.value)}
        />
        <Textarea
          label="Value received"
          name="value_received"
          rows={2}
          value={valueReceived}
          onChange={(e) => setValueReceived(e.currentTarget.value)}
        />
        <Textarea
          label="Follow-up"
          name="follow_up"
          rows={2}
          value={followUp}
          onChange={(e) => setFollowUp(e.currentTarget.value)}
        />

        <label className="log-contact-form__checkbox">
          <input
            type="checkbox"
            checked={advanceState}
            onChange={(e) => setAdvanceState(e.currentTarget.checked)}
          />
          <span>Advance relationship state if conditions met</span>
        </label>

        {error && <p className="log-contact-form__error" role="alert">{error}</p>}

        <div className="log-contact-form__actions">
          <Button variant="ghost" type="button" onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" loading={submitting}>
            Save contact
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

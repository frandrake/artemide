import { useEffect, useState } from 'react';
import { apiPost, ApiError } from '../../lib/api';
import type { OutreachChannel } from '../../lib/types';
import Dialog from '../ui/Dialog';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import Button from '../ui/Button';
import './SendDraftModal.css';

export interface SendDraftModalProps {
  draftUlid: string;
  defaultChannel: OutreachChannel;
  defaultBody: string;
  isOpen: boolean;
  onClose: () => void;
  onSent: () => void;
}

export default function SendDraftModal({
  draftUlid, defaultChannel, defaultBody, isOpen, onClose, onSent,
}: SendDraftModalProps) {
  const [sentAt, setSentAt] = useState<string>('');
  const [sentVia, setSentVia] = useState<OutreachChannel>(defaultChannel);
  const [recipient, setRecipient] = useState('');
  const [summary, setSummary] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setSentAt(new Date().toISOString().slice(0, 16));  // local "YYYY-MM-DDTHH:MM"
      setSentVia(defaultChannel);
      setRecipient('');
      setSummary('');
      setError(null);
    }
  }, [isOpen, defaultChannel]);

  async function handleConfirm() {
    setSubmitting(true);
    setError(null);
    try {
      const idem = `send-${draftUlid}-${Date.now()}`;
      await apiPost(
        '/api/v1/outreach/messages',
        {
          draft_ulid: draftUlid,
          sent_at: sentAt ? new Date(sentAt).toISOString() : undefined,
          sent_via: sentVia,
          recipient_handle: recipient || null,
          contact_summary: summary || null,
        },
        idem,
      );
      onSent();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Send failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      className="send-draft-dialog"
      title="Mark draft as sent"
      children={
        <div className="send-draft__body">
          <p className="send-draft__note">
            Recording the send creates a contact_log entry, advances the partner's stage, and
            freezes this version of the body. The actual message is sent via your usual tool
            (Gmail / LinkedIn / etc.) or by the OpenClaw agent.
          </p>
          <div className="send-draft__row">
            <Input
              type="datetime-local"
              label="Sent at"
              name="sent_at"
              value={sentAt}
              onChange={(e) => setSentAt(e.target.value)}
            />
            <Select
              label="Channel"
              name="sent_via"
              value={sentVia}
              onChange={(e) => setSentVia(e.target.value as OutreachChannel)}
            >
              <option value="email">Email</option>
              <option value="linkedin">LinkedIn</option>
              <option value="message">Message</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <Input
            label="Recipient (email, LinkedIn URL, etc.)"
            name="recipient_handle"
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
          />
          <Textarea
            label="Contact summary (optional — defaults to body excerpt)"
            name="contact_summary"
            rows={3}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
          {error && <div className="send-draft__error" role="alert">{error}</div>}
        </div>
      }
      footer={
        <>
          <Button variant="ghost" type="button" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button
            variant="primary"
            type="button"
            onClick={handleConfirm}
            loading={submitting}
          >
            Confirm send
          </Button>
        </>
      }
    />
  );
}

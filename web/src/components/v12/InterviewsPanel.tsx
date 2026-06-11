import { useEffect, useState } from 'react';
import { apiGet, apiPost, apiPut, ApiError } from '../../lib/api';
import type { Interview, InterviewFormat, TranscriptSource } from '../../lib/types';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';
import { Textarea } from '../ui/Textarea';
import { EmptyState } from '../ui/EmptyState';
import Toast from '../shared/Toast';
import { titleCase } from './helpers';

const FORMATS: InterviewFormat[] = ['onsite', 'video', 'phone', 'other'];

interface Props {
  engagementUlid: string;
}

export default function InterviewsPanel({ engagementUlid }: Props) {
  const [items, setItems] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // log-interview form
  const [date, setDate] = useState('');
  const [round, setRound] = useState('');
  const [fmt, setFmt] = useState<InterviewFormat>('video');
  const [panel, setPanel] = useState('');
  const [summary, setSummary] = useState('');

  // per-row transcript editor
  const [expanded, setExpanded] = useState<string | null>(null);
  const [transcript, setTranscript] = useState('');
  const [transcriptLoading, setTranscriptLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setItems(await apiGet<Interview[]>(`/api/v1/engagements/${engagementUlid}/interviews`));
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : 'Failed to load interviews.');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [engagementUlid]);

  async function logInterview(e: React.FormEvent) {
    e.preventDefault();
    if (!date) { setToast('Interview date is required.'); return; }
    setBusy(true);
    try {
      await apiPost(`/api/v1/engagements/${engagementUlid}/interviews`, {
        interview_date: date,
        round: round ? Number(round) : null,
        format: fmt,
        panel: panel || null,
        summary: summary || null,
      });
      setDate(''); setRound(''); setPanel(''); setSummary('');
      await load();
      setToast('Interview logged.');
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : 'Failed to log interview.');
    } finally {
      setBusy(false);
    }
  }

  async function toggleTranscript(iv: Interview) {
    if (expanded === iv.ulid) { setExpanded(null); return; }
    setExpanded(iv.ulid);
    setTranscript('');
    setTranscriptLoading(true);
    try {
      const full = await apiGet<Interview>(`/api/v1/interviews/${iv.ulid}?include_transcript=true`);
      setTranscript(full.transcript ?? '');
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : 'Failed to load transcript.');
    } finally {
      setTranscriptLoading(false);
    }
  }

  async function saveTranscript(iv: Interview) {
    setBusy(true);
    try {
      await apiPut(`/api/v1/interviews/${iv.ulid}/transcript`, {
        transcript,
        transcript_source: 'manual' as TranscriptSource,
      });
      setExpanded(null);
      setToast('Transcript saved.');
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : 'Failed to save transcript.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card style={{ marginTop: 'var(--space-3)' }}>
      <h2 className="panel-title">Interviews</h2>

      <form onSubmit={logInterview} style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', alignItems: 'flex-end', marginBottom: 'var(--space-3)' }}>
        <Input label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        <Input label="Round" type="number" min={1} value={round} onChange={(e) => setRound(e.target.value)} style={{ maxWidth: 90 }} />
        <Select label="Format" value={fmt} onChange={(e) => setFmt(e.target.value as InterviewFormat)}>
          {FORMATS.map((f) => <option key={f} value={f}>{titleCase(f)}</option>)}
        </Select>
        <Input label="Panel" value={panel} onChange={(e) => setPanel(e.target.value)} placeholder="e.g. CEO, CHRO" />
        <Input label="Summary" value={summary} onChange={(e) => setSummary(e.target.value)} style={{ minWidth: 200, flex: 1 }} />
        <Button type="submit" loading={busy}>Log interview</Button>
      </form>

      {loading ? <p className="rationale">Loading…</p>
        : items.length === 0 ? <EmptyState title="No interviews yet" description="Log the first interview above." />
          : (
            <ul className="timeline">
              {items.map((iv) => (
                <li key={iv.ulid}>
                  <div className="when">{iv.interview_date}</div>
                  <div>
                    {iv.round != null ? `Round ${iv.round}` : 'Interview'}
                    {iv.format ? ` · ${titleCase(iv.format)}` : ''}
                    {iv.panel ? ` · ${iv.panel}` : ''}
                    {iv.summary ? ` — ${iv.summary}` : ''}
                    {iv.transcript_source ? <Badge tone="info" className="badge--inline">transcript</Badge> : null}
                    <div style={{ marginTop: 'var(--space-1)' }}>
                      <Button variant="ghost" size="sm" onClick={() => toggleTranscript(iv)}>
                        {expanded === iv.ulid ? 'Hide transcript' : 'Transcript'}
                      </Button>
                    </div>
                    {expanded === iv.ulid && (
                      <div style={{ marginTop: 'var(--space-2)' }}>
                        {transcriptLoading ? <p className="rationale">Loading transcript…</p> : (
                          <>
                            <Textarea
                              rows={8}
                              value={transcript}
                              onChange={(e) => setTranscript(e.target.value)}
                              placeholder="Paste the verbatim transcript…"
                            />
                            <Button size="sm" loading={busy} onClick={() => saveTranscript(iv)}>Save transcript</Button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}

      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </Card>
  );
}

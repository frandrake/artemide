import { useEffect, useState } from 'react';
import { apiGet, apiPost, ApiError } from '../../lib/api';
import Button from '../ui/Button';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import './IntakeWorkbench.css';

type Domain = 'executive' | 'board';
type Preview = {
  ulid: string;
  status: 'pending' | 'confirmed' | 'rejected';
  proposed_payload: Record<string, unknown>;
  provider: string;
  model: string;
  input_hash: string;
  created_at: string;
  sources: Array<{ source_type?: string; source_url?: string; label?: string }>;
};

async function sha256(value: string) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export default function IntakeWorkbench({ domain }: { domain: Domain }) {
  const [items, setItems] = useState<Preview[]>([]);
  const [raw, setRaw] = useState('');
  const [proposal, setProposal] = useState('{}');
  const [sourceType, setSourceType] = useState('message');
  const [sourceUrl, setSourceUrl] = useState('');
  const [provider, setProvider] = useState('hermes');
  const [model, setModel] = useState('human-reviewed');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setItems(await apiGet<Preview[]>(`/api/v1/intake/${domain}/previews`));
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Could not load previews.'); }
  }
  useEffect(() => { void refresh(); }, [domain]);

  async function stage() {
    setBusy('stage'); setError(null);
    try {
      const parsed = JSON.parse(proposal) as Record<string, unknown>;
      const inputHash = await sha256(raw.trim());
      await apiPost(`/api/v1/intake/${domain}/previews`, {
        proposed_payload: { ...parsed, source_type: sourceType, unstructured_input: raw.trim() },
        provider, model, prompt: 'owner-staged ingestion proposal', input_hash: inputHash,
        sources: [{ source_type: sourceType, source_url: sourceUrl || null, label: 'Owner supplied source' }],
        provenance: { submitted_from: 'web-review-workbench' },
      });
      setRaw(''); setProposal('{}'); await refresh();
    } catch (e) { setError(e instanceof SyntaxError ? 'Proposal must be valid JSON.' : e instanceof ApiError ? e.message : 'Could not stage proposal.'); }
    finally { setBusy(null); }
  }

  async function decide(item: Preview, decision: 'confirm' | 'reject') {
    setBusy(item.ulid); setError(null);
    try {
      await apiPost(`/api/v1/intake/${domain}/previews/${item.ulid}/${decision}`, decision === 'confirm' ? { corrected_payload: item.proposed_payload } : { reason: 'Rejected in review workbench' });
      await refresh();
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Decision failed.'); }
    finally { setBusy(null); }
  }

  return <div className="intake-workbench">
    <section className="intake-compose" aria-labelledby="stage-title">
      <header><p>{domain.toUpperCase()} INTAKE</p><h2 id="stage-title">Stage a proposal</h2></header>
      <div className="intake-compose__meta">
        <Select label="Source type" value={sourceType} onChange={(e) => setSourceType(e.currentTarget.value)}>
          <option value="message">Message</option><option value="cv">CV</option><option value="link">Link</option><option value="notes">Notes</option>
        </Select>
        <label>Source URL<input value={sourceUrl} onChange={(e) => setSourceUrl(e.currentTarget.value)} placeholder="https://…" /></label>
        <label>Provider<input value={provider} onChange={(e) => setProvider(e.currentTarget.value)} /></label>
        <label>Model<input value={model} onChange={(e) => setModel(e.currentTarget.value)} /></label>
      </div>
      <Textarea label="Unstructured source" rows={7} value={raw} onChange={(e) => setRaw(e.currentTarget.value)} placeholder="Paste a message, CV extract, notes or source text…" />
      <Textarea label="Proposed structured fields (JSON)" rows={7} value={proposal} onChange={(e) => setProposal(e.currentTarget.value)} />
      <p className="intake-note">Nothing here updates canonical CRM records. The hash prevents the same source being staged twice; every decision is audited.</p>
      <Button variant="primary" disabled={!raw.trim()} loading={busy === 'stage'} onClick={() => void stage()}>Stage preview</Button>
    </section>

    <section className="intake-queue" aria-labelledby="queue-title">
      <header><p>REVIEW GATE</p><h2 id="queue-title">Preview queue</h2><span>{items.filter((x) => x.status === 'pending').length} pending</span></header>
      {error && <p className="intake-error" role="alert">{error}</p>}
      {items.length === 0 && <p className="intake-empty">No previews staged.</p>}
      <ol>
        {items.map((item) => <li key={item.ulid}>
          <div className="intake-card__head"><strong>{item.status}</strong><time>{new Date(item.created_at).toLocaleDateString('en-GB')}</time></div>
          <pre>{JSON.stringify(item.proposed_payload, null, 2)}</pre>
          <p>{item.provider} · {item.model} · <code>{item.input_hash.slice(0, 12)}</code></p>
          {item.status === 'pending' && <div className="intake-card__actions">
            <Button variant="primary" loading={busy === item.ulid} onClick={() => void decide(item, 'confirm')}>Confirm preview</Button>
            <Button variant="ghost" disabled={busy === item.ulid} onClick={() => void decide(item, 'reject')}>Reject</Button>
          </div>}
        </li>)}
      </ol>
    </section>
  </div>;
}

import { useState } from 'react';
import { apiGet, apiPost, ApiError } from '../../lib/api';
import Button from '../ui/Button';
import Select from '../ui/Select';
import Textarea from '../ui/Textarea';
import './PreparationWorkbench.css';

type Domain = 'executive' | 'board';
type Pack = { ulid: string; version: number; status: 'proposed' | 'confirmed' | 'superseded'; content: string; content_sha256: string; proposed_at: string; sources: Array<{ citation_label: string; public_url?: string }> };

async function digest(value: string) {
  const data = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return Array.from(new Uint8Array(data)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export default function PreparationWorkbench({ domain }: { domain: Domain }) {
  const [targetType, setTargetType] = useState('engagement');
  const [targetUlid, setTargetUlid] = useState('');
  const [content, setContent] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceEvidence, setSourceEvidence] = useState('');
  const [citation, setCitation] = useState('[S1]');
  const [packs, setPacks] = useState<Pack[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!targetUlid.trim()) return;
    setBusy('load'); setError(null);
    try {
      const path = domain === 'board'
        ? `/api/v1/preparation/board?board_opportunity_ulid=${encodeURIComponent(targetUlid.trim())}`
        : `/api/v1/preparation/executive?target_entity_type=${encodeURIComponent(targetType)}&target_entity_ulid=${encodeURIComponent(targetUlid.trim())}`;
      setPacks(await apiGet<Pack[]>(path));
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Could not load packs.'); }
    finally { setBusy(null); }
  }

  async function propose() {
    setBusy('propose'); setError(null);
    try {
      const sourceHash = await digest(sourceEvidence);
      const source = { source_kind: 'public_web', public_url: sourceUrl, sha256: sourceHash, retrieved_at: new Date().toISOString(), citation_label: citation };
      const common = { content, sources: [source], generated_by: 'owner-web-workbench', model: null, prompt_version: 'v1', generation_metadata: { workbench: true } };
      const path = domain === 'board' ? '/api/v1/preparation/board' : '/api/v1/preparation/executive';
      const body = domain === 'board' ? { ...common, board_opportunity_ulid: targetUlid.trim() } : { ...common, target_entity_type: targetType, target_entity_ulid: targetUlid.trim() };
      await apiPost(path, body); await load();
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Could not create pack proposal.'); setBusy(null); }
  }

  async function confirm(pack: Pack) {
    setBusy(pack.ulid); setError(null);
    try { await apiPost(`/api/v1/preparation/${domain}/${pack.ulid}/confirm`); await load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Could not confirm pack.'); setBusy(null); }
  }

  const valid = targetUlid.trim() && content.trim() && sourceUrl.trim() && sourceEvidence.trim() && citation.trim() && content.includes(citation);
  return <div className="prep-workbench">
    <section className="prep-compose">
      <header><p>{domain.toUpperCase()} PREPARATION</p><h2>Propose a source-backed pack</h2></header>
      {domain === 'executive' && <Select label="Target type" value={targetType} onChange={(e) => setTargetType(e.currentTarget.value)}><option value="engagement">Opportunity</option><option value="partner">Contact</option><option value="org">Organisation</option></Select>}
      <label>Target ULID<input value={targetUlid} onChange={(e) => setTargetUlid(e.currentTarget.value)} placeholder={domain === 'board' ? 'Board opportunity ULID' : 'Executive record ULID'} /></label>
      <div className="prep-actions"><Button variant="ghost" loading={busy === 'load'} disabled={!targetUlid.trim()} onClick={() => void load()}>Load versions</Button></div>
      <label>Public source URL<input type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.currentTarget.value)} placeholder="https://…" /></label>
      <Textarea label="Source evidence used (hashed locally)" rows={5} value={sourceEvidence} onChange={(e) => setSourceEvidence(e.currentTarget.value)} />
      <label>Citation label<input value={citation} onChange={(e) => setCitation(e.currentTarget.value)} /></label>
      <Textarea label="Preparation pack" rows={12} value={content} onChange={(e) => setContent(e.currentTarget.value)} placeholder={`Include ${citation} wherever this source supports a claim.`} />
      <p className="prep-note">Every claim should carry a source label. Confirmed versions are immutable; confirming a new version supersedes the prior one.</p>
      <Button variant="primary" loading={busy === 'propose'} disabled={!valid} onClick={() => void propose()}>Create proposed version</Button>
    </section>
    <section className="prep-versions">
      <header><p>VERSION HISTORY</p><h2>Stored packs</h2></header>
      {error && <p className="prep-error" role="alert">{error}</p>}
      {packs.length === 0 && <p className="prep-note">Enter a target ULID and load its versions.</p>}
      <ol>{packs.map((pack) => <li key={pack.ulid}>
        <div><strong>v{pack.version} · {pack.status}</strong><code>{pack.content_sha256.slice(0, 12)}</code></div>
        <pre>{pack.content}</pre>
        {pack.status === 'proposed' && <Button variant="primary" loading={busy === pack.ulid} onClick={() => void confirm(pack)}>Confirm immutable version</Button>}
      </li>)}</ol>
    </section>
  </div>;
}

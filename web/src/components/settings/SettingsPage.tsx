import { useEffect, useState } from 'react';
import { apiGet, apiPost, ApiError } from '../../lib/api';
import type { BackupEntry, SystemInfo } from '../../lib/types';
import Button from '../ui/Button';
import Dialog from '../ui/Dialog';
import Skeleton from '../ui/Skeleton';
import { formatAbsoluteDate } from '../../lib/formatting';
import './SettingsPage.css';

export default function SettingsPage() {
  return (
    <div className="settings">
      <header className="settings__head">
        <h1>Settings</h1>
        <p className="settings__sub">Token rotation, backups, system info.</p>
      </header>
      <TokenCard />
      <BackupCard />
      <SystemCard />
    </div>
  );
}

// ---------- token rotation ----------

function TokenCard() {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    apiGet<SystemInfo>('/api/v1/system/info').then(setInfo).catch(() => undefined);
  }, []);

  async function rotate() {
    setSubmitting(true);
    setError(null);
    try {
      const resp = await apiPost<{ new_token: string }>('/api/v1/admin/rotate-token');
      setNewToken(resp.new_token);
      setConfirmOpen(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Rotation failed.');
    } finally {
      setSubmitting(false);
    }
  }

  function copy(value: string) {
    navigator.clipboard?.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <section className="settings__card">
      <h2>API token</h2>
      <p className="settings__muted">
        Source: <strong>{info?.token_source ?? '…'}</strong>
      </p>
      <p className="settings__token-display">
        <span>Current token:</span>
        <code>••••••••••••</code>
        <span className="settings__muted"> (revealed only once on rotation)</span>
      </p>
      <Button variant="primary" onClick={() => setConfirmOpen(true)}>Rotate token</Button>

      {error && <p className="settings__error" role="alert">{error}</p>}

      {newToken && (
        <div className="settings__token-result" role="status">
          <p><strong>Token rotated.</strong> Copy this now — it will not be shown again.</p>
          <div className="settings__token-row">
            <code>{newToken}</code>
            <Button variant="secondary" size="sm" onClick={() => copy(newToken)}>
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
          <p className="settings__muted">
            Update your Claude MCP server header (<code>Authorization: Bearer …</code>)
            and any external tool configs immediately. The previous token is no longer accepted.
          </p>
        </div>
      )}

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Rotate API token?"
        description="This invalidates the current token immediately. Any active Claude MCP session, tool config, or script using the old token will start returning 401."
        footer={(
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button variant="primary" loading={submitting} onClick={rotate}>Rotate now</Button>
          </>
        )}
      />
    </section>
  );
}

// ---------- backups ----------

function BackupCard() {
  const [backups, setBackups] = useState<BackupEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      const resp = await apiGet<{ backups: BackupEntry[] }>('/api/v1/admin/backups');
      setBackups(resp.backups);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to load backups.');
    } finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, []);

  async function trigger() {
    setTriggering(true);
    setError(null);
    try {
      await apiPost('/api/v1/admin/backup');
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Backup failed.');
    } finally { setTriggering(false); }
  }

  return (
    <section className="settings__card">
      <h2>Backups</h2>
      <p className="settings__muted">
        {backups && backups[0] ? `Last backup: ${formatAbsoluteDate(backups[0].modified_at)}` : 'No backups recorded.'}
      </p>
      <Button variant="secondary" size="sm" loading={triggering} onClick={trigger}>Trigger backup now</Button>

      {loading && <Skeleton width="100%" height={80} />}
      {error && <p className="settings__error" role="alert">{error}</p>}

      {backups && backups.length > 0 && (
        <ul className="settings__backup-list">
          {backups.map((b) => (
            <li key={b.filename}>
              <code>{b.filename}</code>
              <span className="settings__muted">
                {formatAbsoluteDate(b.modified_at)} · {(b.size_bytes / 1024 / 1024).toFixed(1)} MB
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ---------- system ----------

function SystemCard() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<SystemInfo>('/api/v1/system/info').then(setInfo).catch((e) =>
      setError(e instanceof ApiError ? e.message : 'Failed to load system info.'),
    );
  }, []);

  return (
    <section className="settings__card">
      <h2>System</h2>
      {error && <p className="settings__error" role="alert">{error}</p>}
      {!info && !error && <Skeleton width="100%" height={120} />}
      {info && (
        <dl className="settings__system">
          <dt>Schema version</dt>
          <dd>{info.schema_version ?? '—'}{info.schema_applied_at ? ` (applied ${info.schema_applied_at})` : ''}</dd>

          <dt>Build hash</dt>
          <dd><code>{info.build_hash}</code></dd>

          <dt>Token source</dt>
          <dd>{info.token_source}</dd>

          <dt>Counts</dt>
          <dd>
            firms {info.counts.firms} · partners {info.counts.partners} · contacts {info.counts.contacts} ·
            notes {info.counts.notes} · audit {info.counts.audit_entries}
          </dd>

          <dt>Dependencies</dt>
          <dd>
            <ul className="settings__deps">
              {Object.entries(info.dependencies).map(([n, v]) => (
                <li key={n}><code>{n}</code> {v}</li>
              ))}
            </ul>
          </dd>
        </dl>
      )}
    </section>
  );
}

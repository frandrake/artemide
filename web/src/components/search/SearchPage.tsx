import { useEffect, useRef, useState } from 'react';
import { apiGet, ApiError } from '../../lib/api';
import type { SearchHit } from '../../lib/types';
import EmptyState from '../ui/EmptyState';
import Badge from '../ui/Badge';
import './SearchPage.css';

const DEBOUNCE_MS = 300;

function readInitialQuery(): string {
  if (typeof window === 'undefined') return '';
  return new URLSearchParams(window.location.search).get('q') ?? '';
}

const ENTITY_ORDER: SearchHit['entity_type'][] = ['firm', 'partner', 'note', 'contact'];
const ENTITY_LABELS: Record<SearchHit['entity_type'], string> = {
  firm: 'Firms', partner: 'Partners', note: 'Notes', contact: 'Contacts',
};

export default function SearchPage() {
  const [query, setQuery] = useState(readInitialQuery);
  const [debounced, setDebounced] = useState(query);
  const [results, setResults] = useState<SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const callId = useRef(0);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    if (!debounced) { setResults(null); return; }
    const id = ++callId.current;
    setLoading(true);
    setError(null);
    apiGet<SearchHit[]>(`/api/v1/search?q=${encodeURIComponent(debounced)}&limit=30`)
      .then((d) => { if (callId.current === id) setResults(d); })
      .catch((e) => { if (callId.current === id) setError(e instanceof ApiError ? e.message : String(e)); })
      .finally(() => { if (callId.current === id) setLoading(false); });
  }, [debounced]);

  // Keep URL ?q= in sync without triggering a navigation
  useEffect(() => {
    const url = new URL(window.location.href);
    if (debounced) url.searchParams.set('q', debounced);
    else url.searchParams.delete('q');
    window.history.replaceState({}, '', url.toString());
  }, [debounced]);

  const grouped: Record<SearchHit['entity_type'], SearchHit[]> = {
    firm: [], partner: [], note: [], contact: [],
  };
  (results ?? []).forEach((r) => { grouped[r.entity_type]?.push(r); });

  return (
    <div className="search-page">
      <header className="search-page__head">
        <h1>Search</h1>
        <p className="search-page__sub">All firms, partners, notes, contacts.</p>
      </header>

      <div className="search-page__input-wrap">
        <input
          type="search"
          autoFocus
          value={query}
          placeholder="Type to search"
          onChange={(e) => setQuery(e.target.value)}
          className="search-page__input"
          aria-label="Search query"
        />
        {loading && <span className="search-page__loading">searching…</span>}
      </div>

      {error && <p className="search-page__error" role="alert">{error}</p>}

      {!debounced && (
        <EmptyState title="Type to search" description="Names, summaries, notes — anything in the relationship asset." />
      )}

      {debounced && results && results.length === 0 && !loading && (
        <EmptyState title="No matches" description="Try a shorter or alternative term." />
      )}

      {debounced && results && results.length > 0 && (
        <div className="search-page__groups">
          {ENTITY_ORDER.map((type) => {
            const hits = grouped[type];
            if (!hits.length) return null;
            return (
              <section key={type}>
                <h2 className="search-page__group-title">{ENTITY_LABELS[type]}</h2>
                <ul className="search-page__list">
                  {hits.map((h) => (
                    <li key={`${type}-${h.entity_ulid}`}>
                      <a className="search-page__link" href={hrefFor(h)}>
                        <strong>{highlight(h.primary_text, debounced)}</strong>
                      </a>
                      {h.secondary_text && (
                        <p className="search-page__snippet">{highlight(h.secondary_text, debounced)}</p>
                      )}
                      <Badge tone="neutral">{type}</Badge>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function hrefFor(hit: SearchHit): string {
  switch (hit.entity_type) {
    case 'firm': return `/firms/${hit.entity_ulid}`;
    case 'partner': return `/partners/${hit.entity_ulid}`;
    case 'note': return '/notes';
    case 'contact': return '/audit/log';
  }
}

function highlight(text: string, term: string): React.ReactNode {
  if (!term) return text;
  const lower = text.toLowerCase();
  const lowerTerm = term.toLowerCase();
  const out: React.ReactNode[] = [];
  let cursor = 0;
  while (cursor < text.length) {
    const i = lower.indexOf(lowerTerm, cursor);
    if (i === -1) { out.push(text.slice(cursor)); break; }
    if (i > cursor) out.push(text.slice(cursor, i));
    out.push(<mark key={i}>{text.slice(i, i + term.length)}</mark>);
    cursor = i + term.length;
  }
  return out;
}

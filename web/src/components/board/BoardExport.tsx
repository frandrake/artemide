import './board.css';

const CSV_ENTITIES = ['board_firm', 'board_contact', 'board_opportunity', 'board_evaluation'];

export default function BoardExport() {
  return (
    <div className="bd-detail">
      <section className="bd-panel">
        <h2>Markdown ledger</h2>
        <p className="bd-subhead">The full board ledger (tiers → firms → contacts → opportunities). Round-trips with import.</p>
        <a className="bd-btn" href="/api/v1/board/export/markdown" download style={{ display: 'inline-block', marginTop: 'var(--space-1)' }}>
          Download board ledger (.md)
        </a>
      </section>
      <section className="bd-panel">
        <h2>CSV (per entity)</h2>
        <div className="bd-card__meta">
          {CSV_ENTITIES.map((e) => (
            <a key={e} className="bd-btn bd-btn--ghost" href={`/api/v1/board/export/csv?entity_type=${e}`} download>
              {e.replace('board_', '')}.csv
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}

import { useState } from 'react';
import { apiPost } from '../../lib/api';
import { BOARD_EVAL_DIMENSIONS, BOARD_HARD_DISQUALIFIERS } from '../../lib/types';
import type { BoardEvaluation } from '../../lib/types';
import { previewEvaluation, titleCase, verdictTone } from './helpers';
import './board.css';

function initialScores(ev: BoardEvaluation | null | undefined): Record<string, number> {
  const s: Record<string, number> = {};
  for (const d of BOARD_EVAL_DIMENSIONS) {
    const v = ev ? (ev as unknown as Record<string, unknown>)[`score_${d.key}`] : null;
    s[d.key] = typeof v === 'number' ? v : 3;
  }
  return s;
}

export default function EvaluationForm({
  opportunityUlid, evaluation, onSaved,
}: { opportunityUlid: string; evaluation: BoardEvaluation | null | undefined; onSaved: () => void }) {
  const [scores, setScores] = useState<Record<string, number>>(initialScores(evaluation));
  const [disq, setDisq] = useState<string[]>(evaluation?.hard_disqualifiers ?? []);
  const [notes, setNotes] = useState(evaluation?.firo_b_fit_notes ?? '');
  const [busy, setBusy] = useState(false);

  const preview = previewEvaluation(scores, disq);

  function toggle(key: string) {
    setDisq((d) => (d.includes(key) ? d.filter((k) => k !== key) : [...d, key]));
  }

  async function save() {
    setBusy(true);
    try {
      await apiPost(`/api/v1/board/opportunities/${opportunityUlid}/evaluate`, {
        opportunity_ulid: opportunityUlid,
        ...Object.fromEntries(BOARD_EVAL_DIMENSIONS.map((d) => [`score_${d.key}`, scores[d.key]])),
        hard_disqualifiers: disq,
        firo_b_fit_notes: notes || null,
      });
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {BOARD_EVAL_DIMENSIONS.map((d) => (
        <div className="bd-eval-row" key={d.key}>
          <span className="bd-eval-row__label">{d.label}</span>
          <span className="bd-eval-row__weight">×{d.weight}%</span>
          <select value={scores[d.key]} onChange={(e) => setScores((s) => ({ ...s, [d.key]: Number(e.target.value) }))}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      ))}

      <div className="bd-disq">
        <strong style={{ fontSize: 'var(--text-sm)' }}>Hard disqualifiers (any forces a Pass)</strong>
        {BOARD_HARD_DISQUALIFIERS.map((h) => (
          <label key={h.key}>
            <input type="checkbox" checked={disq.includes(h.key)} onChange={() => toggle(h.key)} />
            <span>{h.label}</span>
          </label>
        ))}
      </div>

      <div className="bd-field">
        <label htmlFor="firo">FIRO-B / fit notes</label>
        <textarea id="firo" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>

      <div className="bd-eval-total">
        <span>Weighted total: {preview.weighted.toFixed(2)} / 5</span>
        <span className={`bd-pill ${verdictTone(preview.verdict)}`}>
          {titleCase(preview.verdict)}{preview.forcedPass ? ' (forced)' : ''}
        </span>
      </div>
      <button className="bd-btn" disabled={busy} onClick={save} style={{ marginTop: 'var(--space-2)' }}>
        Save evaluation
      </button>
    </div>
  );
}

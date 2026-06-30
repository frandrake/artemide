import { BOARD_EVAL_DIMENSIONS } from '../../lib/types';
import type { BoardVerdict } from '../../lib/types';

export function titleCase(s: string): string {
  return s.replace(/_/g, ' ');
}

export function boardUlidFromPath(prefix: string): string | null {
  if (typeof window === 'undefined') return null;
  const m = window.location.pathname.match(new RegExp(`^/board/${prefix}/([0-9A-HJKMNP-TV-Z]{26})/?$`, 'i'));
  return m ? m[1] : null;
}

export function verdictTone(v: BoardVerdict | null | undefined): string {
  if (!v) return '';
  return `bd-pill--verdict-${v}`;
}

/** Mirrors src/services/board_evaluation_service.compute_board_evaluation. */
export function previewEvaluation(scores: Record<string, number>, disqualifiers: string[]) {
  const totalWeight = BOARD_EVAL_DIMENSIONS.reduce((a, d) => a + d.weight, 0);
  let sum = 0;
  for (const d of BOARD_EVAL_DIMENSIONS) sum += (scores[d.key] ?? 0) * d.weight;
  const weighted = Math.round((sum / totalWeight) * 100) / 100;
  const forcedPass = disqualifiers.length > 0;
  let verdict: BoardVerdict;
  if (forcedPass) verdict = 'pass';
  else if (weighted >= 4.0) verdict = 'proceed';
  else if (weighted >= 3.0) verdict = 'proceed_with_caution';
  else verdict = 'pass';
  return { weighted, verdict, forcedPass };
}

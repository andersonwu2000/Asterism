/*
 * Bench — "stop this task without stopping the run" (owner's ruling;
 * `POST /api/problems/{p}/bench` | `/unbench`, 743a234d).
 *
 * A benched task takes no further dispatch and no Strategist seat, and
 * keeps every goal, revision and your standing word: it is a pause, not
 * a reset, and it is the only reversible answer to "stop this one".
 * Stop halts the whole engine; parking a goal is final. Neither is
 * this.
 *
 * The endpoints are idempotent, so the console never has to read the
 * current flag before it is safe to press — but it must post the
 * DIRECTION the reader asked for, which is the one thing that can be
 * got backwards.
 */

export function benchPath(problem: string, benched: boolean): string {
  return `/api/problems/${encodeURIComponent(problem)}/${benched ? 'bench' : 'unbench'}`
}

import { ApiError } from './api'
import type { DaemonStatus } from './types'

/*
 * "The engine could not look" is not a reading.
 *
 * `daemon_status` folded every failure into (-1, -1) until `c30bba77`,
 * so a schema the running code may not migrate surfaced as
 * `in_flight: -1` — minus one agent, which is a MEASUREMENT. The
 * counts are null now and `schema` says why, and the console owes the
 * same distinction: where the numbers cannot be read it says so in one
 * line, rather than drawing a panel of instruments over a dial nobody
 * turned.
 *
 * A serve older than the field is NOT behind: it counted, and its
 * numbers are real. Absent must therefore read as "ok", never as the
 * degraded state — the opposite default would put this line over every
 * console talking to a bundle that predates the field.
 *
 * The same fact reaches the console by TWO doors, and the second is
 * the one that fires in production: `_ro` (serve/app.py) refuses a
 * read-only connection to a behind schema, so every endpoint that
 * opens one — `/api/run` included — answers 503 UPGRADE_REQUIRED
 * before its body (and its `daemon.schema` field) is ever built. Both
 * doors are read here so no surface has to spell the predicate itself:
 * ui.tsx's ErrorState had the only copy, and a second one is how two
 * screens start disagreeing about what a 503 meant.
 */

export const SCHEMA_BEHIND_LINE = 'engine on an older schema — restart it'

export function schemaBehind(d: DaemonStatus | null | undefined): boolean {
  return d?.schema === 'behind'
}

export function schemaBehindError(e: unknown): boolean {
  return e instanceof ApiError && e.detail.startsWith('UPGRADE_REQUIRED')
}

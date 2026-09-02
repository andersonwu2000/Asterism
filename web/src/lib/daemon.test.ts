import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { SCHEMA_BEHIND_LINE, schemaBehind, schemaBehindError } from './daemon'
import type { DaemonStatus } from './types'

/*
 * `daemon_status` carries `schema` since `c30bba77`: when the on-disk
 * schema is behind this engine's code, a read-only consumer may not
 * migrate, so nothing was counted and the counts come back null. The
 * console's obligation is to tell "I could not look" from a reading —
 * and, crucially, to tell it from a serve too old to have the field,
 * where every count is real.
 */

const status = (over: Partial<DaemonStatus> = {}): DaemonStatus =>
  ({
    running: false,
    starting: false,
    pid: null,
    scope: null,
    started_at: null,
    stopping: false,
    in_flight_leases: 0,
    gateway: null,
    slots: null,
    last_exit: null,
    ...over,
  }) as DaemonStatus

describe('schemaBehind', () => {
  it('is true only when the engine says so', () => {
    expect(schemaBehind(status({ schema: 'behind' }))).toBe(true)
    expect(schemaBehind(status({ schema: 'ok' }))).toBe(false)
  })

  it('a serve older than the field is not behind — it counted fine', () => {
    expect(schemaBehind(status())).toBe(false)
    expect(schemaBehind(null)).toBe(false)
    expect(schemaBehind(undefined)).toBe(false)
  })

  it('names the action, not the condition', () => {
    // the line has to tell the reader what to DO; a gate that only
    // states a fact leaves them nothing to press
    expect(SCHEMA_BEHIND_LINE).toContain('restart')
  })
})

describe('schemaBehindError', () => {
  it('reads the 503 the read-only connection raises', () => {
    // `_ro` (serve/app.py) refuses the whole endpoint before the body
    // is built, so on /api/run the fact arrives as an error, not a field
    const e = new ApiError(
      503,
      'UPGRADE_REQUIRED: database schema v3 < expected v49; run the engine once to migrate',
    )
    expect(schemaBehindError(e)).toBe(true)
  })

  it('is not every degraded answer — only this one', () => {
    expect(schemaBehindError(new ApiError(404, 'NO_DATABASE'))).toBe(false)
    expect(schemaBehindError(new ApiError(503, 'DB_UNAVAILABLE: locked'))).toBe(false)
  })

  it('a transport failure is not a schema answer', () => {
    expect(schemaBehindError(new Error('Failed to fetch'))).toBe(false)
    expect(schemaBehindError(null)).toBe(false)
    expect(schemaBehindError(undefined)).toBe(false)
  })
})

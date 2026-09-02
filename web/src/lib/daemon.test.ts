import { describe, expect, it } from 'vitest'
import { SCHEMA_BEHIND_LINE, schemaBehind } from './daemon'
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

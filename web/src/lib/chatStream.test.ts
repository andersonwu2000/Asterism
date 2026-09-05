import { describe, expect, it } from 'vitest'
import {
  emptyTurn,
  parseSseFrames,
  reduceEvent,
  rowsFromRecord,
  summarizeTools,
  toolLine,
} from './chatStream'
import type { ToolRow } from './chatStream'

/*
 * The turn's whole grammar (assistant_redesign_2026-09-06.md §3). The
 * panel renders it; this file owns whether it is right, because a
 * stream is the one thing a rendering test cannot hold still.
 */

const frame = (o: Record<string, unknown>) => `data: ${JSON.stringify(o)}\n\n`

describe('SSE frames', () => {
  it('reads complete frames and keeps the partial one for the next chunk', () => {
    const buf = frame({ type: 'delta', text: 'a' }) + frame({ type: 'delta', text: 'b' }) +
      'data: {"type":"del'
    const { events, rest } = parseSseFrames(buf)
    expect(events).toEqual([
      { type: 'delta', text: 'a' },
      { type: 'delta', text: 'b' },
    ])
    expect(rest).toBe('data: {"type":"del')
  })

  it('ignores the keepalive comment the backend writes every 15s', () => {
    // a comment line is the liveness signal, not an event: parsing it
    // as one would put `: keepalive` through JSON.parse on every wake
    const { events, rest } = parseSseFrames(': keepalive\n\n' + frame({ type: 'done', ok: true }))
    expect(events).toEqual([{ type: 'done', ok: true }])
    expect(rest).toBe('')
  })

  it('skips a malformed frame without losing the ones after it', () => {
    const { events } = parseSseFrames('data: not json\n\n' + frame({ type: 'delta', text: 'x' }))
    expect(events).toEqual([{ type: 'delta', text: 'x' }])
  })
})

describe('reducing a turn', () => {
  it('appends a running row on tool_start and settles it on tool_end', () => {
    let t = emptyTurn()
    t = reduceEvent(t, { type: 'tool_start', id: 'a', name: 'inspect', input: { path: 'TREE.md' } }, 1000)
    expect(t.rows).toHaveLength(1)
    expect(t.rows[0]).toMatchObject({ id: 'a', name: 'inspect', running: true, startedAt: 1000 })
    t = reduceEvent(t, { type: 'tool_end', id: 'a', ok: true, ms: 1210, result: 'root …' }, 2210)
    expect(t.rows).toHaveLength(1)
    expect(t.rows[0]).toMatchObject({ running: false, ok: true, ms: 1210, result: 'root …' })
  })

  it('settles the row the end names, not the last one started', () => {
    let t = emptyTurn()
    t = reduceEvent(t, { type: 'tool_start', id: 'a', name: 'inspect', input: {} }, 1000)
    t = reduceEvent(t, { type: 'tool_start', id: 'b', name: 'loogle', input: {} }, 1100)
    t = reduceEvent(t, { type: 'tool_end', id: 'a', ok: true, ms: 300 }, 1300)
    expect(t.rows[0].running).toBe(false)
    expect(t.rows[1].running).toBe(true)
  })

  it('appends a settled row for an end whose start never arrived', () => {
    // never drop what the engine said: a lost start is our gap, not
    // the machine's silence
    let t = emptyTurn()
    t = reduceEvent(t, { type: 'tool_end', id: 'z', name: 'loogle', ok: false, ms: 90 }, 5000)
    expect(t.rows).toHaveLength(1)
    expect(t.rows[0]).toMatchObject({ id: 'z', name: 'loogle', running: false, ok: false, ms: 90 })
    // the row still spans real time, so the wall clock stays honest
    expect(t.rows[0].startedAt).toBe(4910)
  })

  it('carries the stage line until prose starts', () => {
    let t = emptyTurn()
    t = reduceEvent(t, { type: 'status', stage: 'thinking' }, 1)
    expect(t.stage).toBe('thinking')
    t = reduceEvent(t, { type: 'delta', text: 'The task ' }, 2)
    t = reduceEvent(t, { type: 'delta', text: 'is waiting.' }, 3)
    expect(t.stage).toBeNull()
    expect(t.text).toBe('The task is waiting.')
  })

  it('done ends the turn and leaves nothing pulsing', () => {
    let t = emptyTurn()
    t = reduceEvent(t, { type: 'tool_start', id: 'a', name: 'compute', input: {} }, 1000)
    t = reduceEvent(t, { type: 'done', ok: true, subtype: 'success' }, 4000)
    expect(t.done).toBe(true)
    expect(t.ok).toBe(true)
    expect(t.rows[0].running).toBe(false)
  })

  it('an abnormal end and an error both keep whatever streamed', () => {
    let t = emptyTurn()
    t = reduceEvent(t, { type: 'delta', text: 'half an ' }, 1)
    t = reduceEvent(t, { type: 'error', detail: 'no word from the explainer for 600 s' }, 2)
    expect(t.text).toBe('half an ')
    expect(t.ok).toBe(false)
    expect(t.done).toBe(true)
    expect(t.note).toBe('no word from the explainer for 600 s')

    let u = emptyTurn()
    u = reduceEvent(u, { type: 'done', ok: false, subtype: 'error_max_turns' }, 1)
    expect(u.ok).toBe(false)
    expect(u.note).toContain('error_max_turns')
  })
})

describe('the argument summary', () => {
  it('follows the key priority, not the object order', () => {
    expect(toolLine('inspect', { limit: 20, path: 'Problems/Erdos/p1/TREE.md' })).toBe(
      'Problems/Erdos/p1/TREE.md',
    )
    // path outranks query where both are present
    expect(toolLine('search', { query: 'Nat.Prime', path: 'a.lean' })).toBe('a.lean')
    expect(toolLine('loogle', { query: 'Nat.Prime ?p' })).toBe('Nat.Prime ?p')
  })

  it('falls back to the first string, and to nothing at all', () => {
    expect(toolLine('odd', { depth: 3, subject: 'the root' })).toBe('the root')
    expect(toolLine('daemon_status', {})).toBe('')
    expect(toolLine('odd', { depth: 3, deep: { path: 'x' } })).toBe('')
  })

  it('is one line, unquoted, and 80 chars at most', () => {
    expect(toolLine('compute', { expr: 'sum of\nfirst 40 primes' })).toBe('sum of⏎first 40 primes')
    expect(toolLine('compute', { expr: '"quoted"' })).toBe('quoted')
    const long = toolLine('inspect', { path: 'x'.repeat(200) })
    expect(long).toHaveLength(80)
    expect(long.endsWith('…')).toBe(true)
  })
})

describe('the collapsed line', () => {
  const row = (name: string, startedAt: number, ms: number): ToolRow => ({
    id: `${name}${startedAt}`,
    name,
    input: {},
    startedAt,
    ms,
    ok: true,
    result: null,
    running: false,
  })

  it('counts by family and spans the whole turn', () => {
    expect(
      summarizeTools([
        row('inspect', 0, 1200),
        row('Read', 1300, 400),
        row('read_project_doc', 1800, 400),
        row('loogle', 2300, 10_100),
      ]),
    ).toBe('read 3 files · searched Mathlib once · 12.4s')
  })

  it('names an unknown tool rather than dropping it', () => {
    expect(summarizeTools([row('prepare_command', 0, 500)])).toBe('prepare_command · 0.5s')
    expect(summarizeTools([row('Grep', 0, 500), row('Glob', 600, 400)])).toBe(
      'searched the workspace ×2 · 1.0s',
    )
  })

  it('says nothing about a turn that used no tools', () => {
    expect(summarizeTools([])).toBe('')
  })
})

describe('a turn read back from disk', () => {
  it('reconstructs the timeline sequentially — the record keeps durations, not clocks', () => {
    const rows = rowsFromRecord([
      { id: 'a', name: 'inspect', input: { path: 'TREE.md' }, ok: true, ms: 1200, result: 'x' },
      { id: 'b', name: 'loogle', input: {}, ok: false, ms: 800, result: null },
    ])
    expect(rows.map((r) => r.startedAt)).toEqual([0, 1200])
    expect(rows.every((r) => !r.running)).toBe(true)
    expect(summarizeTools(rows)).toBe('read 1 file · searched Mathlib once · 2.0s')
  })

  it('survives a record with no tools at all', () => {
    expect(rowsFromRecord(undefined)).toEqual([])
  })
})

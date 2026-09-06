import { describe, expect, it } from 'vitest'
import { rowTarget } from './timeline'
import type { TimelineEvent } from './types'

/*
 * The log's third field is a NAME the reader can act on, and its click
 * opens THAT object (DESIGN.md). This is the whole of which object.
 */

function ev(over: Partial<TimelineEvent> = {}): TimelineEvent {
  return {
    at: '2026-09-06T04:00:00Z',
    kind: 'theorized',
    object_kind: 'theory',
    label: 'Is the surplus floor forced?',
    goal_id: null,
    n: null,
    note: null,
    body: null,
    path: null,
    approx: false,
    id: 'tf1',
    batch_id: null,
    group_id: null,
    object_group_id: null,
    ...over,
  }
}

const DOC = 'Problems/Combinatorics/_docs/agent/g693_20260906-1612_floor.md'

describe('rowTarget', () => {
  it('opens the star a goal row names', () => {
    expect(rowTarget(ev({ kind: 'proved', object_kind: 'goal', goal_id: 42 }))).toEqual({
      kind: 'goal',
      id: 42,
      problem: null,
    })
  })

  it('opens the revision a Programme row is about, under the log`s own task', () => {
    expect(
      rowTarget(ev({ kind: 'rev', object_kind: 'programme', rev_id: 412 }), 'C.uc'),
    ).toEqual({ kind: 'revision', problem: 'C.uc', revId: 412 })
  })

  it('prefers the row`s own task over the reader`s scope', () => {
    expect(
      rowTarget(
        ev({ kind: 'rev', object_kind: 'programme', rev_id: 412, problem: 'C.other' }),
        'C.uc',
      ),
    ).toEqual({ kind: 'revision', problem: 'C.other', revId: 412 })
  })

  it('opens nothing for a Programme row on a feed that names no task', () => {
    expect(rowTarget(ev({ kind: 'rev', object_kind: 'programme', rev_id: 412 }))).toBeNull()
  })

  /* The theory layer's three landing rows all produce a FILE, and all
   * three must open it. `theorized` was the hole: it is the row a
   * reader reaches for — "the theorist came back, show me what it
   * wrote" — and it opened the request's own history instead (owner,
   * 2026-09-06). */
  it('opens the document the wake produced, not the request`s history', () => {
    expect(rowTarget(ev({ kind: 'theorized', path: DOC }))).toEqual({
      kind: 'document',
      path: DOC,
    })
  })

  it('opens the document on the accepted and the refused landing alike', () => {
    for (const kind of ['theory', 'theory_refused']) {
      expect(rowTarget(ev({ kind, n: 3, path: DOC }))).toEqual({
        kind: 'document',
        path: DOC,
      })
    }
  })

  it('opens nothing when the wake landed no file — a link into a 404 is worse', () => {
    expect(rowTarget(ev({ kind: 'theorized', note: 'failed' }))).toBeNull()
    expect(rowTarget(ev({ kind: 'theory_died', note: 'failed' }))).toBeNull()
  })

  it('opens nothing for a request that has not been answered yet', () => {
    expect(rowTarget(ev({ kind: 'asked_theory' }))).toBeNull()
    expect(rowTarget(ev({ kind: 'theorizing' }))).toBeNull()
  })
})

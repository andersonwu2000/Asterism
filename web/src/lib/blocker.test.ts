import { describe, expect, it } from 'vitest'
import { topBlocker } from '../components/Timeline'
import type { TimelineEvent } from './types'

/* The blocker is DERIVED from the log rather than passed in, so that
 * the run-wide view (several problems merged) gets it on the same
 * terms as one problem's page. That derivation is the whole claim the
 * line makes, so it is worth pinning. */

let n = 0
function ev(kind: string, label: string, at: string, attempt?: number): TimelineEvent {
  n += 1
  return {
    at, kind, object_kind: 'goal', label, goal_id: 1,
    n: attempt ?? null, note: null, body: null, approx: false,
    id: `e${n}`, batch_id: null, group_id: null, object_group_id: null,
  }
}

describe('topBlocker', () => {
  it('is nothing when nothing has failed', () => {
    expect(topBlocker([ev('proved', 'a', '3'), ev('asked', 'b', '2')])).toBeNull()
  })

  it('names the goal with the most recorded failures', () => {
    const b = topBlocker([
      ev('failed', 'a', '1'),
      ev('failed', 'b', '2'),
      ev('failed', 'b', '3'),
    ])
    expect(b?.label).toBe('b')
    expect(b?.failures).toBe(2)
  })

  it('counts rows, not an ordinal the engine never agreed to', () => {
    // failures are `dead_attempts` records; `goals.attempts` is a
    // different number and disagrees in both directions, so the line
    // counts what it can see and says so
    const b = topBlocker([ev('failed', 'a', '1'), ev('failed', 'a', '2')])
    expect(b?.failures).toBe(2)
  })

  it('drops a goal that landed after its attempts', () => {
    // the count is about what is STILL in the way; a brick that fought
    // and then landed is the machine working, not a blocker
    const b = topBlocker([
      ev('failed', 'a', '1'),
      ev('failed', 'a', '2'),
      ev('proved', 'a', '3'),
      ev('failed', 'b', '4'),
    ])
    expect(b?.label).toBe('b')
  })

  it('drops one that was set aside or died, not only one that landed', () => {
    expect(topBlocker([ev('failed', 'a', '1'), ev('shelved', 'a', '2')])).toBeNull()
    expect(topBlocker([ev('failed', 'a', '1'), ev('dead', 'a', '2')])).toBeNull()
  })

  it('counts a revived goal again once it is re-attempted', () => {
    // proved -> reopened -> attempted: it is back in the way, and a
    // "did it ever settle?" test would have missed it
    const b = topBlocker([
      ev('failed', 'a', '1'),
      ev('proved', 'a', '2'),
      ev('reopened', 'a', '3'),
      ev('failed', 'a', '4'),
    ])
    expect(b?.label).toBe('a')
    expect(b?.failures).toBe(2)
  })

  it('ignores hiccups — an infra death cost no attempt', () => {
    expect(topBlocker([ev('hiccup', 'a', '1')])).toBeNull()
  })
})

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

  it('names the goal with the most failed attempts', () => {
    const b = topBlocker([
      ev('attempt', 'a', '1', 1),
      ev('attempt', 'b', '2', 1),
      ev('attempt', 'b', '3', 2),
    ])
    expect(b?.label).toBe('b')
    expect(b?.n).toBe(2)
  })

  it('drops a goal that landed after its attempts', () => {
    // the count is about what is STILL in the way; a brick that fought
    // and then landed is the machine working, not a blocker
    const b = topBlocker([
      ev('attempt', 'a', '1', 1),
      ev('attempt', 'a', '2', 2),
      ev('proved', 'a', '3'),
      ev('attempt', 'b', '4', 1),
    ])
    expect(b?.label).toBe('b')
  })

  it('drops one that was set aside or died, not only one that landed', () => {
    expect(topBlocker([ev('attempt', 'a', '1', 3), ev('set_aside', 'a', '2')])).toBeNull()
    expect(topBlocker([ev('attempt', 'a', '1', 3), ev('dead', 'a', '2')])).toBeNull()
  })

  it('counts a revived goal again once it is re-attempted', () => {
    // proved -> reopened -> attempted: it is back in the way, and a
    // "did it ever settle?" test would have missed it
    const b = topBlocker([
      ev('attempt', 'a', '1', 1),
      ev('proved', 'a', '2'),
      ev('reopened', 'a', '3'),
      ev('attempt', 'a', '4', 2),
    ])
    expect(b?.label).toBe('a')
    expect(b?.n).toBe(2)
  })

  it('ignores hiccups — an infra death cost no attempt', () => {
    expect(topBlocker([ev('hiccup', 'a', '1')])).toBeNull()
  })
})

import { describe, expect, it } from 'vitest'
import { agentRows, theoryLine } from './docShelf'
import type { DocEntry, TheoryMeta } from './docShelf'

/** An ISO stamp built from LOCAL parts, so the line this file expects
 * is the line the reader's own clock draws — wherever the suite runs. */
function at(y: number, mon: number, d: number, h: number, min: number): string {
  return new Date(y, mon - 1, d, h, min).toISOString()
}

function meta(over: Partial<TheoryMeta> = {}): TheoryMeta {
  return {
    group_id: 5,
    created_at: at(2026, 9, 4, 16, 12),
    status: 'accepted',
    rounds: 2,
    objective: 'what breaks the counting?',
    verdict: ['criterion 1: …', 'criterion 2: …', 'criterion 3: …', 'criterion 4: …'],
    ...over,
  }
}

function doc(path: string, theory?: TheoryMeta): DocEntry {
  return { path, kind: 'file', size: 10, ...(theory ? { theory } : {}) }
}

describe('agentRows', () => {
  it('reads only the agent area, and never the area folder itself', () => {
    const rows = agentRows([
      { path: 'user', kind: 'dir' },
      doc('user/notes.md'),
      { path: 'agent', kind: 'dir' },
      doc('agent/notes.md'),
    ])
    expect(rows.map((e) => e.path)).toEqual(['agent/notes.md'])
  })

  it('puts what the theory layer wrote above the rest of the shelf', () => {
    const rows = agentRows([
      { path: 'agent', kind: 'dir' },
      doc('agent/aaa.md'),
      doc('agent/g5_20260904-1612_x.md', meta()),
    ])
    expect(rows.map((e) => e.path)).toEqual([
      'agent/g5_20260904-1612_x.md',
      'agent/aaa.md',
    ])
  })

  it('reads the newest theory document first — a shelf is not alphabetical', () => {
    const rows = agentRows([
      doc('agent/a_old.md', meta({ created_at: at(2026, 9, 1, 9, 0) })),
      doc('agent/z_new.md', meta({ created_at: at(2026, 9, 4, 16, 12) })),
    ])
    expect(rows.map((e) => e.path)).toEqual(['agent/z_new.md', 'agent/a_old.md'])
  })

  it('leaves everything else in the order the tree gave it', () => {
    const rows = agentRows([
      { path: 'agent', kind: 'dir' },
      { path: 'agent/papers', kind: 'dir' },
      doc('agent/papers/abc/text.md'),
      doc('agent/papers/abc/map.md'),
      doc('agent/zzz.md'),
    ])
    expect(rows.map((e) => e.path)).toEqual([
      'agent/papers',
      'agent/papers/abc/text.md',
      'agent/papers/abc/map.md',
      'agent/zzz.md',
    ])
  })

  it('leaves the caller`s array alone — the shelf is read, not rewritten', () => {
    const entries = [doc('agent/a.md'), doc('agent/b.md', meta())]
    agentRows(entries)
    expect(entries.map((e) => e.path)).toEqual(['agent/a.md', 'agent/b.md'])
  })
})

describe('theoryLine', () => {
  it('names the group, the day and what the review cost', () => {
    expect(theoryLine(meta())).toBe('G5 · 4 Sep 16:12 · accepted, 2 rounds')
  })

  it('omits the group when the document was written for no group', () => {
    expect(theoryLine(meta({ group_id: null }))).toBe('4 Sep 16:12 · accepted, 2 rounds')
  })

  it('counts one round as one round', () => {
    expect(theoryLine(meta({ rounds: 1 }))).toBe('G5 · 4 Sep 16:12 · accepted, 1 round')
  })

  it('says what it knows when the stamp is unreadable', () => {
    expect(theoryLine(meta({ created_at: 'not a date' }))).toBe('G5 · accepted, 2 rounds')
  })
})

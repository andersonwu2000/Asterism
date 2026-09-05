import { describe, expect, it } from 'vitest'
import { canSwitchModel, deriveTitle, sortSessions, truncateAt } from './chatSessions'
import type { ChatSessionSummary, ChatTurn, ModelGroup } from './types'

/*
 * The session list's own laws (assistant_redesign_2026-09-06.md §2).
 * `deriveTitle` is a MIRROR of the backend's rule: the panel shows a
 * title the instant the first question is typed, and the two must
 * agree or the row renames itself when the reload lands.
 */

const summary = (over: Partial<ChatSessionSummary>): ChatSessionSummary => ({
  id: 'c1',
  title: 'why is p1 stalled?',
  created_at: '2026-09-06T10:00:00Z',
  updated_at: '2026-09-06T10:00:00Z',
  turns: 2,
  model: 'claude-sonnet-5',
  provider: 'claude',
  ...over,
})

const GROUPS: ModelGroup[] = [
  { provider: 'claude', models: ['claude-sonnet-5', 'claude-opus-5'], source: 'declared', installed: true },
  { provider: 'antigravity', models: ['gemini-3.6-flash-high'], source: 'probe', installed: true },
]

describe('the title a conversation wears', () => {
  it('is the first line, whitespace collapsed', () => {
    expect(deriveTitle('why is p1 stalled?\n\nand what next?')).toBe('why is p1 stalled?')
    expect(deriveTitle('  why   is\tp1 stalled?  ')).toBe('why is p1 stalled?')
  })

  it('clips at 60 characters and says so', () => {
    const t = deriveTitle('x'.repeat(200))
    expect(t).toHaveLength(60)
    expect(t.endsWith('…')).toBe(true)
  })

  it('derives nothing from nothing — the row says "new conversation" itself', () => {
    expect(deriveTitle('')).toBe('')
    expect(deriveTitle('\n\n')).toBe('')
  })
})

describe('the list', () => {
  it('is newest first', () => {
    const rows = [
      summary({ id: 'a', updated_at: '2026-09-06T09:00:00Z' }),
      summary({ id: 'b', updated_at: '2026-09-06T11:00:00Z' }),
      summary({ id: 'c', updated_at: '2026-09-06T10:00:00Z' }),
    ]
    expect(sortSessions(rows).map((s) => s.id)).toEqual(['b', 'c', 'a'])
    // the poll's array is shared with the render that is on screen
    expect(rows.map((s) => s.id)).toEqual(['a', 'b', 'c'])
  })
})

describe('edit & re-ask', () => {
  const turns: ChatTurn[] = [
    { role: 'user', text: 'first', at: '2026-09-06T10:00:00Z' },
    { role: 'assistant', text: 'answer', at: '2026-09-06T10:00:10Z' },
    { role: 'user', text: 'second', at: '2026-09-06T10:01:00Z' },
    { role: 'assistant', text: 'answer 2', at: '2026-09-06T10:01:20Z' },
  ]

  it('drops the turn being re-asked and everything after it', () => {
    expect(truncateAt(turns, 2)).toEqual(turns.slice(0, 2))
    expect(truncateAt(turns, 0)).toEqual([])
  })

  it('refuses anywhere but a user turn — the backend refuses it too', () => {
    expect(truncateAt(turns, 1)).toBeNull()
    expect(truncateAt(turns, 4)).toBeNull()
    expect(truncateAt(turns, -1)).toBeNull()
  })
})

describe('switching backends mid-conversation', () => {
  it('is fine before the first question', () => {
    expect(canSwitchModel(summary({ turns: 0 }), GROUPS, 'gemini-3.6-flash-high')).toBe(true)
    expect(canSwitchModel(null, GROUPS, 'gemini-3.6-flash-high')).toBe(true)
  })

  it('is refused once the conversation has turns — the handle belongs to one CLI', () => {
    expect(canSwitchModel(summary({}), GROUPS, 'gemini-3.6-flash-high')).toBe(false)
    expect(canSwitchModel(summary({}), GROUPS, 'claude-opus-5')).toBe(true)
  })

  it('invents no refusal for a model nobody offers', () => {
    // an override may name anything; the server's 422 names the offer,
    // and "start a new conversation" would not be the way out
    expect(canSwitchModel(summary({}), GROUPS, 'some-private-build')).toBe(true)
  })
})

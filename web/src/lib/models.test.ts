import { describe, expect, it } from 'vitest'
import { draftForPick, explainerGroups, pickerRows, providerForModel } from './models'
import type { PickerHeader } from './models'
import type { ModelGroup } from './types'

const GROUPS: ModelGroup[] = [
  { provider: 'claude', models: ['claude-opus-5', 'claude-sonnet-5'], source: 'declared', installed: true },
  { provider: 'antigravity', models: ['gemini-3.7-flash-high'], source: 'probe', installed: true },
  { provider: 'codex', models: ['gpt-5.6-luna'], source: 'declared', installed: false },
]

describe('one picker, two settings', () => {
  it('names the backend that runs a model', () => {
    expect(providerForModel(GROUPS, 'gemini-3.7-flash-high')).toBe('antigravity')
    expect(providerForModel(GROUPS, 'gpt-5.6-luna')).toBe('codex')
  })

  it('invents no owner for a name nobody offers', () => {
    // an env/yaml override may name anything; guessing would move the
    // seat to a backend the reader never chose
    expect(providerForModel(GROUPS, 'some-private-build')).toBeNull()
  })

  it('moves the backend with the model — the whole point', () => {
    expect(draftForPick(GROUPS, 'formalizer.model', 'formalizer.provider',
                        'gemini-3.7-flash-high')).toEqual({
      'formalizer.model': 'gemini-3.7-flash-high',
      'formalizer.provider': 'antigravity',
    })
  })

  it('writes the model alone when no backend claims it', () => {
    // better a seat whose backend is untouched than one silently
    // pointed somewhere new
    expect(draftForPick(GROUPS, 'formalizer.model', 'formalizer.provider',
                        'some-private-build')).toEqual({
      'formalizer.model': 'some-private-build',
    })
  })

  it('offers a model from a backend that is not installed', () => {
    // the accounts panel answers "installed"; refusing the choice here
    // would make the two panels argue, and the picker labels it
    expect(providerForModel(GROUPS, 'gpt-5.6-luna')).toBe('codex')
  })
})

describe('the models the Assistant may actually seat', () => {
  // `/api/models/refresh` answers for every backend on the machine; only
  // the ones with an explainer can answer a question, and `/api/chat/state`
  // is the list of those. A refreshed group nobody can seat offered a
  // model that dies at the spawn (field test, 2026-09-06).
  const STATE: ModelGroup[] = [
    { provider: 'claude', models: ['claude-sonnet-5'], source: 'declared', installed: true },
    { provider: 'antigravity', models: ['gemini-3.6-flash-high'], source: 'declared', installed: true },
  ]

  it('keeps the probe honest but drops the backends that cannot explain', () => {
    const live: ModelGroup[] = [
      { provider: 'claude', models: ['claude-sonnet-5', 'claude-opus-5'], source: 'probe', installed: true },
      { provider: 'codex', models: ['gpt-5.6-luna'], source: 'declared', installed: false },
      { provider: 'antigravity', models: ['gemini-3.6-flash-high'], source: 'probe', installed: true },
    ]
    const out = explainerGroups(STATE, live)
    expect(out.map((g) => g.provider)).toEqual(['claude', 'antigravity'])
    // the probe's list wins where it answered
    expect(out[0].models).toEqual(['claude-sonnet-5', 'claude-opus-5'])
  })

  it('is the seat list itself until a probe answers', () => {
    expect(explainerGroups(STATE, null)).toEqual(STATE)
  })

  it('never loses a seat the probe was silent about', () => {
    const live: ModelGroup[] = [
      { provider: 'claude', models: ['claude-opus-5'], source: 'probe', installed: true },
    ]
    const out = explainerGroups(STATE, live)
    expect(out.map((g) => g.provider)).toEqual(['claude', 'antigravity'])
    expect(out[1].source).toBe('declared')
  })
})

describe('the picker is a hierarchy, not a flat list', () => {
  it('opens each provider with a header row and hangs its models under it', () => {
    const rows = pickerRows(GROUPS)
    expect(rows.map((r) => r.kind)).toEqual([
      'header', 'model', 'model', 'header', 'model', 'header', 'model',
    ])
    expect(rows[0]).toEqual({
      kind: 'header', provider: 'claude', note: ' — list not live',
    })
    expect(rows[1]).toEqual({
      kind: 'model', provider: 'claude', model: 'claude-opus-5',
    })
  })

  it('says on the HEADER what is true of the whole provider', () => {
    // "not installed" and "list not live" are facts about the backend,
    // not about any one model — repeated on every row they would be
    // the same fact drawn N times
    const rows = pickerRows(GROUPS)
    const headers = rows.filter((r): r is PickerHeader => r.kind === 'header')
    expect(headers.map((h) => `${h.provider}${h.note}`)).toEqual([
      'claude — list not live',
      'antigravity',
      'codex (not installed) — list not live',
    ])
  })

  it('draws no header for a provider that offers nothing', () => {
    expect(
      pickerRows([{ provider: 'codex', models: [], source: 'probe', installed: true }]),
    ).toEqual([])
  })

  it('carries a model the offer does not name, so the seat stays visible', () => {
    // an env/yaml override may seat anything; a picker that dropped it
    // would show the reader a value nobody chose
    const rows = pickerRows(GROUPS, 'some-private-build')
    expect(rows[0]).toEqual({ kind: 'header', provider: 'set outside this list', note: '' })
    expect(rows[1]).toEqual({
      kind: 'model', provider: 'set outside this list', model: 'some-private-build',
    })
    // and it is not repeated once it IS in the offer
    expect(pickerRows(GROUPS, 'claude-opus-5')[0]).toEqual({
      kind: 'header', provider: 'claude', note: ' — list not live',
    })
  })
})

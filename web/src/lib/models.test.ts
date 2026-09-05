import { describe, expect, it } from 'vitest'
import { draftForPick, explainerGroups, providerForModel } from './models'
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

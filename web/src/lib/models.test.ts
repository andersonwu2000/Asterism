import { describe, expect, it } from 'vitest'
import { draftForPick, providerForModel } from './models'
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

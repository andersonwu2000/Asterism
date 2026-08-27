import { describe, expect, it } from 'vitest'
import { boxDiags, engineWord } from './leanSession'
import type { LeanSessionState } from './leanSession'

const diag = (message: string) => ({
  line: null,
  col: null,
  severity: '3',
  message,
})

describe('a box owns its own output, and never the file s', () => {
  it('never hands a box the unplaceable bin', () => {
    // the regression, in the shape it actually took: two `#check`
    // results, both `line: null`, both filed under preamble by serve
    const s = {
      parts: { defs: [diag('defs error')], root: [] },
      preamble: [diag('1 + 1 : N'), diag('2 + 2 : N')],
    } as unknown as LeanSessionState
    expect(boxDiags(s, 'defs')).toEqual([diag('defs error')])
    expect(boxDiags(s, 'root')).toEqual([])
    for (const part of ['defs', 'root'])
      for (const d of boxDiags(s, part))
        expect(s.preamble).not.toContain(d)
  })

  it('gives an unknown box nothing rather than throwing', () => {
    const s = { parts: {}, preamble: [diag('x')] } as unknown as LeanSessionState
    expect(boxDiags(s, 'nope')).toEqual([])
  })
})

describe('one ladder of engine words', () => {
  const say = (phase: LeanSessionState['phase'], detail: string | null = null) =>
    engineWord({ phase, detail })

  it('speaks for every phase that is not steady', () => {
    for (const phase of ['dormant', 'warming', 'busy', 'connecting', 'checking'] as const)
      expect(say(phase), phase).not.toBe('')
  })

  it('says nothing when the engine is ready and well', () => {
    expect(say('ready')).toBe('')
    expect(say('idle')).toBe('')
  })

  it('surfaces an error detail rather than swallowing it', () => {
    expect(say('ready', 'slot exploded')).toContain('slot exploded')
  })
})

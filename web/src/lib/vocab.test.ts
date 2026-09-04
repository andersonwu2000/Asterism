import { describe, expect, it } from 'vitest'
import {
  EVENT_CLS,
  decisionKindLabel,
  decisionKindTitle,
  eventLabel,
  eventTitle,
  isTheory,
} from './vocab'

/* The theory layer's words. `Theorize` is the one kind the Timeline
 * reads RAW — serve has no verb mapping for it (timeline.py
 * `_decision_events`), so the decision kind arrives on the event where
 * every other row carries a lowercase verb. Both maps therefore have to
 * answer to the same string, and this file is what says so. */
describe('the theory layer', () => {
  it('names a Theorize row in the reader words', () => {
    expect(eventLabel('Theorize')).toBe('asked for theory')
  })

  it('names a Theorize decision in the same words as its row', () => {
    // one fact must not have two names across two surfaces
    expect(decisionKindLabel('Theorize')).toBe('asked for theory')
    expect(decisionKindLabel('Theorize')).toBe(eventLabel('Theorize'))
  })

  it('says in both tooltips what a theorist answers with', () => {
    // the engine term stays greppable, and the sentence has to name the
    // product — a document, reviewed before it lands
    for (const t of [eventTitle('Theorize'), decisionKindTitle('Theorize')]) {
      expect(t).toContain('engine term: Theorize')
      expect(t).toContain('document')
    }
  })

  it('leaves the verb quiet — asking for theory is the norm', () => {
    expect(EVENT_CLS.Theorize).toBe('text-ink-dim')
  })

  it('wears the page mark on both of its names', () => {
    // the decision (Timeline) and the worker (Engine room) are one
    // thing wearing one glyph
    expect(isTheory('Theorize')).toBe(true)
    expect(isTheory('Theorist')).toBe(true)
  })

  it('wears it on nothing else', () => {
    for (const kind of ['Strategist', 'Formalizer', 'Librarian', 'Inject', 'theory', ''])
      expect(isTheory(kind)).toBe(false)
  })
})

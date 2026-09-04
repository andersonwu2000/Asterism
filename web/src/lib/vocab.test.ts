import { describe, expect, it } from 'vitest'
import {
  EVENT_CLS,
  countWord,
  decisionKindLabel,
  decisionKindTitle,
  eventLabel,
  eventTitle,
  isTheory,
} from './vocab'

/* The theory layer's words. REQUIREMENT CHANGED (serve `602c6614`): the
 * layer's whole life is on the log now — the request, the wake at both
 * ends, and the answer — as five lowercase verbs under
 * `object_kind: 'theory'`. The raw decision kind `Theorize` no longer
 * reaches an event row (serve mints `asked_theory` for it), so the row
 * words moved onto the minted verbs; the DECISION-side words stay,
 * because a decision is still a decision. */
describe('the theory layer', () => {
  const KINDS = ['asked_theory', 'theorizing', 'theorized', 'theory', 'theory_refused']

  it('names the request row in the reader words', () => {
    expect(eventLabel('asked_theory')).toBe('asked for theory')
  })

  it('names a Theorize decision in the same words as the row it mints', () => {
    // one fact must not have two names across two surfaces
    expect(decisionKindLabel('Theorize')).toBe('asked for theory')
    expect(decisionKindLabel('Theorize')).toBe(eventLabel('asked_theory'))
  })

  it('no longer keeps a row word for the raw decision kind', () => {
    // serve mints the verb now; a second key for it is the drift
    expect(eventLabel('Theorize')).toBe('Theorize')
  })

  it('names the wake at both ends', () => {
    expect(eventLabel('theorizing')).toBe('theorist at work')
    expect(eventLabel('theorized')).toBe('theorist came back')
  })

  it('names the two ways an answer arrives', () => {
    expect(eventLabel('theory')).toBe('theory landed')
    expect(eventLabel('theory_refused')).toBe('theory refused')
  })

  it('keeps every one of its verbs inside three words', () => {
    // the verb column is 6.2rem — a verb that wraps costs every row
    for (const kind of KINDS)
      expect(eventLabel(kind).split(' ').length).toBeLessThanOrEqual(3)
  })

  it('says in both Theorize tooltips what a theorist answers with', () => {
    // the engine term stays greppable, and the sentence has to name the
    // product — a document, reviewed before it lands
    for (const t of [eventTitle('asked_theory'), decisionKindTitle('Theorize')]) {
      expect(t).toContain('engine term: Theorize')
      expect(t).toContain('document')
    }
  })

  it('keeps the engine term greppable on every one of its rows', () => {
    for (const kind of KINDS) expect(eventTitle(kind)).toMatch(/^engine term: /)
  })

  it('leaves the request and the wake quiet — asking is the norm', () => {
    expect(EVENT_CLS.asked_theory).toBe('text-ink-dim')
    expect(EVENT_CLS.theorizing).toBe('text-ink-dim')
    expect(EVENT_CLS.theorized).toBe('text-ink-dim')
  })

  it('lights a landed document like the other landings, and a refusal like residue', () => {
    expect(EVENT_CLS.theory).toBe('text-star')
    expect(EVENT_CLS.theory_refused).toBe('text-ink-faint')
  })

  it('wears the page mark on every row of its life, and on its worker', () => {
    // the five rows (Timeline) and the worker it seats (Engine room)
    // are one thing wearing one glyph
    for (const kind of KINDS) expect(isTheory(kind)).toBe(true)
    expect(isTheory('Theorist')).toBe(true)
  })

  it('wears it on nothing else', () => {
    // `Theorize` included: the DECISION kind never reaches a row now,
    // and the mark is worn by rows and workers, not by decisions
    for (const kind of ['Theorize', 'Strategist', 'Formalizer', 'Librarian', 'Inject', ''])
      expect(isTheory(kind)).toBe(false)
  })
})

/* The count beside the verb. It is an attempt number on most rows and
 * reads as one; on a theory row it is what the REVIEW cost, and a bare
 * `2` beside "theory landed" reads as the second document. */
describe('countWord', () => {
  it('counts a document`s review rounds in words', () => {
    expect(countWord('theory', 3)).toBe('3 rounds')
  })

  it('says a single round in the singular', () => {
    expect(countWord('theory', 1)).toBe('1 round')
  })

  it('counts a refusal`s rounds the same way — it paid them too', () => {
    expect(countWord('theory_refused', 2)).toBe('2 rounds')
  })

  it('leaves every other row`s count the bare number it already was', () => {
    expect(countWord('failed', 2)).toBe('2')
    expect(countWord('rev', 11)).toBe('11')
  })
})

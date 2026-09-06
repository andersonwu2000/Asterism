import { describe, expect, it } from 'vitest'
import {
  EVENT_CLS,
  EVENT_KINDS,
  TIMELINE_LABEL_MAX,
  countWord,
  cycleLine,
  decisionKindLabel,
  decisionKindTitle,
  eventColumn,
  eventLabel,
  eventTitle,
  isTheory,
} from './vocab'

/* The theory layer's words. REQUIREMENT CHANGED (serve `602c6614`): the
 * layer's whole life is on the log now — the request, the wake at both
 * ends, and the answer — as six lowercase verbs under
 * `object_kind: 'theory'`. The raw decision kind `Theorize` no longer
 * reaches an event row (serve mints `asked_theory` for it), so the row
 * words moved onto the minted verbs; the DECISION-side words stay,
 * because a decision is still a decision. */
describe('the theory layer', () => {
  const KINDS = [
    'asked_theory', 'theorizing', 'theorized', 'theory', 'theory_refused',
    'theory_died',
  ]

  it('names the request row in the reader words', () => {
    expect(eventLabel('asked_theory')).toBe('theorize')
  })

  it('names a Theorize decision in the same words as the row it mints', () => {
    // one fact must not have two names across two surfaces
    expect(decisionKindLabel('Theorize')).toBe('theorize')
    expect(decisionKindLabel('Theorize')).toBe(eventLabel('asked_theory'))
  })

  it('no longer keeps a row word for the raw decision kind', () => {
    // serve mints the verb now; a second key for it is the drift
    expect(eventLabel('Theorize')).toBe('Theorize')
  })

  it('names the wake at both ends', () => {
    expect(eventLabel('theorizing')).toBe('theorizing')
    expect(eventLabel('theorized')).toBe('theorized')
  })

  it('names the three ways an answer arrives', () => {
    // REQUIREMENT CHANGED 2026-09-05: a wake can also die before
    // anything is reviewed, and that is an answer of its own — reading
    // it as a refusal is what union_closed g691 did twice.
    expect(eventLabel('theory')).toBe('theory')
    expect(eventLabel('theory_refused')).toBe('refused')
    expect(eventLabel('theory_died')).toBe('died')
  })

  it('says it in the plain verb the rest of the log speaks in', () => {
    // the PAGE mark is what says "theory" on these rows, so the verb
    // does not have to say it again — and a verb that repeats the mark
    // is what made this column wider than every other row on the page
    // (owner, 2026-09-06). One word each, as `proved` and `shelved`
    // are one word.
    for (const kind of KINDS) expect(eventLabel(kind).split(' ')).toHaveLength(1)
  })

  it('says a death was never read, so nobody refused it', () => {
    expect(eventTitle('theory_died')).toContain('Not a refusal')
    expect(eventTitle('theory_died')).not.toContain('reviewer refused')
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
    // a death is residue too — an infra hiccup takes the same ink
    expect(EVENT_CLS.theory_died).toBe('text-ink-faint')
  })

  it('wears the page mark on every row of its life, and on its worker', () => {
    // the six rows (Timeline) and the worker it seats (Engine room)
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
 * `2` beside "theory" reads as the second document. */
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

/* The review cycle, narrated. One sentence shape for both arguments the
 * machine holds with a reviewer — a Programme proposal and a theory
 * document — because a reader learns the rhythm once; the NOUN changes,
 * so a Theorist card never claims to be drafting a programme. */
describe('cycleLine', () => {
  const at = (phase: string, round: number, objections: string[] = []) =>
    ({ phase, round, objections, since_sec: null }) as never

  it('narrates a document with the document`s own words', () => {
    expect(cycleLine(at('drafting', 0), 'document')).toBe(
      'writing the document — the reviewer reads it next',
    )
    expect(cycleLine(at('judging', 1), 'document')).toBe(
      'round 1 — the reviewer is examining the document',
    )
    expect(cycleLine(at('revising', 2, ['a', 'b']), 'document')).toBe(
      'round 2 — rejected with 2 objections; revising the document',
    )
    expect(cycleLine(at('passed', 2), 'document')).toBe(
      'round 2 — passed review; landing the document under Documents',
    )
  })

  it('keeps the programme`s words for the strategist', () => {
    expect(cycleLine(at('proposing', 0), 'programme')).toBe(
      'drafting a programme proposal — the adversarial reviewer reads it next',
    )
    expect(cycleLine(at('revising', 1, ['a']), 'programme')).toBe(
      'round 1 — rejected with 1 objection; revising the proposal',
    )
    expect(cycleLine(at('passed', 3), 'programme')).toBe(
      'round 3 — passed review; committing the programme',
    )
  })

  it('shows how long the reviewer has been out', () => {
    expect(
      cycleLine({ phase: 'judging', round: 1, objections: [], since_sec: 90 }, 'document'),
    ).toBe('round 1 — the reviewer is examining the document (1m 30s)')
  })
})

describe("the Timeline's label column", () => {
  /* The widest count each kind can print. Two digits wherever the
   * number is an attempt or a revision — `rev 12` is an ordinary row —
   * and the review rounds on the two theory rows, which
   * `theorist.rounds` caps (default 3, `Tooling/pipeline/theorist`). */
  const widestCount = (kind: string) =>
    kind === 'theory' || kind === 'theory_refused' ? 3 : 12

  it('is spent to the character — MAX is the widest column it can print', () => {
    // "do not leave slack" (owner, 2026-09-06): the column is the app's
    // narrow one, and MAX is what the VOCABULARY costs, not a number
    // picked to be comfortable. Whichever way the vocabulary moves —
    // a longer verb, or a shorter one that frees width back to the
    // objective — this is the line that has to move with it.
    const widths = EVENT_KINDS.map((k) => eventColumn(k, widestCount(k)).length)
    expect(Math.max(...widths)).toBe(TIMELINE_LABEL_MAX)
  })

  it('fits every verb the vocabulary can print', () => {
    // The column is FIXED — a state label that reflowed would make
    // every row's objective start somewhere else — so its width is a
    // promise about this table. It was sized at ~15 characters for a
    // vocabulary that had grown to 18, and the overflow painted over
    // the objective beside it ("theorist at workSettle: DOES AN A…").
    // The truncation in the track is the safety net; no verb here may
    // actually reach for it.
    const over = EVENT_KINDS.filter((k) => eventLabel(k).length > TIMELINE_LABEL_MAX)
    expect(over, `${over.map((k) => `${k} → ${eventLabel(k)}`).join(', ')}`).toEqual([])
  })

  it('says the count in the same breath as the verb', () => {
    expect(eventColumn('failed', 3)).toBe('failed 3')
    expect(eventColumn('theory', 2)).toBe('theory 2 rounds')
    // a row with nothing to count says only the verb — a trailing
    // separator with no number is ink for a fact that is not there
    expect(eventColumn('proved', null)).toBe('proved')
  })
})

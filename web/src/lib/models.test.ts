import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import {
  boardDrafts,
  draftForPick,
  explainerGroups,
  houseInEffect,
  offCatalog,
  pickerRows,
  pinnedSeats,
  providerForModel,
  seatRows,
} from './models'
import type { HouseBoard, PickerHeader } from './models'
import type { ConfigSetting, ModelGroup } from './types'

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

describe('a seat, read out of the flat settings list', () => {
  const S = (key: string, resolved: string, over: Partial<ConfigSetting> = {}) =>
    ({
      key,
      yaml: null,
      resolved,
      type: 'str',
      description: '',
      ...over,
    }) as ConfigSetting

  const SETTINGS: ConfigSetting[] = [
    S('formalizer.model', 'claude-sonnet-5'),
    S('strategist.model', 'gpt-5.6-luna'),
    S('dispatch.pool', '2', { type: 'int' }),
    S('formalizer.provider', 'claude'),
    S('strategist.provider', 'codex'),
    S('formalizer.reasoning_effort', 'xhigh', { applies: false }),
    S('strategist.reasoning_effort', 'high', { applies: true }),
  ]

  it('gathers a seat\'s three keys into the one thing they describe', () => {
    // the wire is flat because `set_ui_setting` writes one key at a
    // time; a SEAT is what the reader is actually setting
    const rows = seatRows(SETTINGS)
    expect(rows.map((r) => r.seat)).toEqual(['formalizer', 'strategist'])
    expect(rows[0].model?.resolved).toBe('claude-sonnet-5')
    expect(rows[0].provider?.resolved).toBe('claude')
    expect(rows[0].effort?.resolved).toBe('xhigh')
    // and a knob that belongs to no seat is not one
    expect(rows.some((r) => r.seat === 'dispatch')).toBe(false)
  })

  it('says when the seated model is not in the offer', () => {
    // the yaml routinely seats a tier the declared list has not caught
    // up with; the row must show what IS seated and say it is off-list
    // rather than silently redrawing it as something else
    expect(offCatalog(GROUPS, 'claude-opus-5')).toBe(false)
    expect(offCatalog(GROUPS, 'claude-fable-5-1')).toBe(true)
    expect(offCatalog(GROUPS, '')).toBe(false)
  })
})

describe('one choice seats a whole board', () => {
  // the derivation itself is the engine's (`serve/model_catalog`,
  // pinned by pytest); these are the readings the page makes of it
  const CLAUDE: HouseBoard = {
    theorist: { provider: 'claude', model: 'claude-fable-5-1' },
    theory_reviewer: { provider: 'claude', model: 'claude-fable-5-1' },
    strategist: { provider: 'claude', model: 'claude-opus-5' },
    adversary: { provider: 'claude', model: 'claude-opus-5' },
    formalizer: { provider: 'claude', model: 'claude-sonnet-5' },
  }
  const GPT: HouseBoard = {
    theorist: { provider: 'codex', model: 'gpt-6-astra', effort: 'xhigh' },
    theory_reviewer: { provider: 'codex', model: 'gpt-6-astra', effort: 'xhigh' },
    strategist: { provider: 'codex', model: 'gpt-5.6-sol', effort: 'high' },
    adversary: { provider: 'codex', model: 'gpt-5.6-sol', effort: 'high' },
    formalizer: { provider: 'codex', model: 'gpt-5.6-terra', effort: 'medium' },
  }
  const S = (key: string, resolved: string, over: Partial<ConfigSetting> = {}) =>
    ({ key, yaml: null, resolved, type: 'str', description: '', ...over }) as ConfigSetting
  const seats = (over: Record<string, string> = {}): ConfigSetting[] =>
    Object.entries(CLAUDE).flatMap(([seat, s]) => [
      S(`${seat}.model`, over[seat] ?? s.model),
      S(`${seat}.provider`, over[seat] ? 'codex' : s.provider),
    ])

  it('writes a seat key per derived seat, and a depth only where one is derived', () => {
    // the existing seat-write path takes one key at a time; this is
    // what the page hands it, and nothing outside the seats
    expect(boardDrafts({ strategist: CLAUDE.strategist })).toEqual({
      'strategist.model': 'claude-opus-5',
      'strategist.provider': 'claude',
    })
    expect(boardDrafts({ strategist: GPT.strategist })).toEqual({
      'strategist.model': 'gpt-5.6-sol',
      'strategist.provider': 'codex',
      'strategist.reasoning_effort': 'high',
    })
  })

  it('names the seats that sit off the board — an override is a pin', () => {
    expect(pinnedSeats(seatRows(seats()), CLAUDE)).toEqual([])
    expect(pinnedSeats(seatRows(seats({ formalizer: 'gpt-5.6-luna' })), CLAUDE))
      .toEqual(['formalizer'])
    // a seat the board says nothing about is not pinned by silence
    expect(pinnedSeats(seatRows(seats()), { strategist: CLAUDE.strategist }))
      .toEqual([])
  })

  it('reads which house the machine is on, and refuses to guess a tie', () => {
    const houses = { claude: CLAUDE, codex: GPT }
    expect(houseInEffect(seatRows(seats()), houses)).toBe('claude')
    // one pinned seat does not move the house
    expect(houseInEffect(seatRows(seats({ formalizer: 'gpt-5.6-luna' })), houses))
      .toBe('claude')
    // nothing derived = nothing to be on
    expect(houseInEffect(seatRows(seats()), { claude: {}, codex: {} })).toBeNull()
  })
})

describe('one picker template, on every surface that seats a model', () => {
  /* The Assistant, the run parameters and the settings page all ask the
   * same question, and each used to draw its own control: a hand-rolled
   * `<optgroup>` select in two of them, `ModelPicker` in the third, and
   * the grouping the owner could not see (2026-09-06) existed in only
   * one. A second drawing of one control is the drift this pins — the
   * import is the observable, since none of these render in this
   * environment. */
  const surfaces = ['AssistantPanel', 'RunParameters', 'Seats', 'DefaultModel']

  it('draws every model choice with the one component', () => {
    for (const name of surfaces) {
      const src = readFileSync(new URL(`../components/${name}.tsx`, import.meta.url), 'utf8')
      expect(src, `${name} builds its own model list`).not.toContain('<optgroup')
    }
  })

  it('reaches that component by importing it, not by copying it', () => {
    for (const name of surfaces.filter((n) => n !== 'DefaultModel')) {
      const src = readFileSync(new URL(`../components/${name}.tsx`, import.meta.url), 'utf8')
      expect(src, `${name} has no picker`).toMatch(/from '\.\/ModelPicker'/)
    }
  })
})

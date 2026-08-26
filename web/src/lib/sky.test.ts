import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  ALIAS_DASH,
  CITE_DASH,
  citeInk,
  edgeStroke,
  nodeStyle,
  radius,
} from './sky'
import type { Goal, GoalStatus } from './types'

/*
 * The sky's ink law, made mechanical.
 *
 * Twice the owner read shelved and proved as the same dot, and twice
 * the answer was "nudge the brightness" — 45% -> 55% on 2026-08-24,
 * and still not enough. Eyeballing a ratio is what kept failing, so
 * the law stopped being a paragraph to remember: a status that carries
 * a proof and one that does not may never differ by brightness alone,
 * and "differ" is a MEASURED distance on the ground the sky is painted
 * on, not a number that looked bigger in a diff.
 *
 * The axis stayed brightness by the owner's call (2026-08-26: shelved
 * gets darker, not hollow), which is exactly why the floor below has
 * to be mechanical — the same knob that drifted here twice is still
 * the one holding the two apart.
 */

// The palette is READ, not restated: a test that hardcodes #f4f5f8
// stops testing the day someone retunes index.css, which is exactly
// the day it needs to speak up. `@theme` is the dark ground — the sky
// is only ever painted there. (Read off disk, not imported: vitest
// stubs every `.css` id to an empty string, `?raw` included.)
const CSS = readFileSync(
  fileURLToPath(new URL('../index.css', import.meta.url)),
  'utf8',
)
const DARK = CSS.slice(0, CSS.indexOf('\n}'))

function token(name: string): [number, number, number] {
  const m = DARK.match(new RegExp(`--color-${name}:\\s*([^;]+);`))
  if (!m) throw new Error(`no --color-${name} in the dark palette`)
  const hex = m[1].trim()
  const rgba = hex.match(/rgba?\(([^)]+)\)/)
  if (rgba) {
    const n = rgba[1].split(',').map((s: string) => Number(s))
    const a = n[3] ?? 1
    // an rgba token is already composited against the page ground
    return [0, 1, 2].map((i) => a * n[i] + (1 - a) * 10) as [number, number, number]
  }
  const h = hex.replace('#', '')
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as [
    number,
    number,
    number,
  ]
}

/** resolve the tiny CSS subset the marks use: a var(), or one
 * color-mix of two of them */
function resolve(paint: string): [number, number, number] {
  const mix = paint.match(
    /color-mix\(in srgb,\s*var\(--color-([\w-]+)\)\s*([\d.]+)%,\s*var\(--color-([\w-]+)\)\s*\)/,
  )
  if (mix) {
    const a = token(mix[1])
    const b = token(mix[3])
    const p = Number(mix[2]) / 100
    return [0, 1, 2].map((i) => p * a[i] + (1 - p) * b[i]) as [
      number,
      number,
      number,
    ]
  }
  const v = paint.match(/var\(--color-([\w-]+)\)/)
  if (!v) throw new Error(`unresolvable paint: ${paint}`)
  return token(v[1])
}

const lin = (c: number): number => {
  const s = c / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}

/** perceived lightness of a mark once it is painted on the sky's
 * ground at its own opacity — what the EYE gets, not what the token
 * says */
function lightness(paint: string, opacity: number): number {
  const bg = token('bg')
  const [r, g, b] = resolve(paint)
  const c = [r, g, b].map((v, i) => opacity * v + (1 - opacity) * bg[i])
  const Y = 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])
  return Y > 0.008856 ? 116 * Math.cbrt(Y) - 16 : 903.3 * Y
}

const goal = (status: GoalStatus, over: Partial<Goal> = {}): Goal =>
  ({
    id: 1,
    slug: 's',
    status,
    kind: 'theorem',
    origin: 'backward',
    depth: 1,
    detached: false,
    alias_target_id: null,
    is_deliverable: false,
    statement: '',
    lean_path: 'proofs/p/A.lean',
    created_at: '',
    attempts: 0,
    dead_attempts: 0,
    in_flight: false,
    ...over,
  }) as Goal

const ALL: GoalStatus[] = [
  'open',
  'attempting',
  'proved',
  'shelved',
  'pending_strategist_review',
  'disproved',
  'frozen',
  'dead',
]

/** the statuses that make `hasLive` true in Constellation — the sky's
 * ink inversion is gated on exactly these */
const LIVE: GoalStatus[] = ['open', 'attempting', 'pending_strategist_review']

/** a mark is a BODY if it is painted through, a SHELL if only its
 * outline is */
const isBody = (fill: string): boolean => fill !== 'transparent'

describe('star marks', () => {
  it('gives every status a resolvable mark', () => {
    for (const s of ALL) {
      for (const hasLive of [true, false]) {
        const m = nodeStyle(goal(s), hasLive)
        expect(() => lightness(m.stroke, m.opacity)).not.toThrow()
        expect(m.opacity).toBeGreaterThan(0)
      }
    }
  })

  it('never separates a proof from a non-proof by brightness alone', () => {
    // THE law. Two marks may sit close in brightness only if something
    // else — body/shell, or the glow — already told them apart. 25 is
    // the gap the owner could not read at 19 (proved 53.0 vs shelved
    // 33.8, measured on union_closed, 2026-08-26).
    for (const hasLive of [true, false]) {
      const proved = nodeStyle(goal('proved'), hasLive)
      for (const s of ALL) {
        if (s === 'proved') continue
        // `hasLive` is derived FROM the goals, so a settled sky cannot
        // hold a live star — comparing that pair would test a picture
        // that never renders (and would demand the settled trophy dim
        // itself for a frontier that isn't there)
        if (!hasLive && LIVE.includes(s)) continue
        const other = nodeStyle(goal(s), hasLive)
        const sameKind = isBody(proved.fill) === isBody(other.fill)
        const sameGlow = proved.glow === other.glow
        const gap = Math.abs(
          lightness(proved.stroke, proved.opacity) -
            lightness(other.stroke, other.opacity),
        )
        expect(
          !sameKind || !sameGlow || gap >= 25,
          `proved vs ${s} (hasLive=${hasLive}): same mark kind, same glow, only ΔL*=${gap.toFixed(1)} apart`,
        ).toBe(true)
      }
    }
  })

  it('draws a shell only where the question closed with no light', () => {
    for (const hasLive of [true, false]) {
      expect(isBody(nodeStyle(goal('proved'), hasLive).fill)).toBe(true)
      expect(isBody(nodeStyle(goal('open'), hasLive).fill)).toBe(true)
      expect(isBody(nodeStyle(goal('attempting'), hasLive).fill)).toBe(true)
      // parked is not closed (owner, 2026-08-26): shelved and frozen
      // stay discs and buy their distance in brightness instead
      expect(isBody(nodeStyle(goal('shelved'), hasLive).fill)).toBe(true)
      expect(isBody(nodeStyle(goal('frozen'), hasLive).fill)).toBe(true)
      for (const s of ['disproved', 'dead'] as const) {
        expect(
          isBody(nodeStyle(goal(s), hasLive).fill),
          `${s} must be a shell`,
        ).toBe(false)
      }
    }
  })

  it('parks frozen exactly like shelved (owner, 2026-08-24)', () => {
    expect(nodeStyle(goal('frozen'), true)).toEqual(nodeStyle(goal('shelved'), true))
  })

  it('keeps dead the floor of the sky', () => {
    // abandoned is the faintest thing drawn — residue, and still never
    // hidden (the sky is always complete)
    const L = (s: GoalStatus): number => {
      const m = nodeStyle(goal(s), true)
      return lightness(m.stroke, m.opacity)
    }
    for (const s of ALL) {
      if (s === 'dead') continue
      expect(L('dead'), `dead must sit under ${s}`).toBeLessThan(L(s))
    }
  })

  it('keeps shelved readable — parked, not buried', () => {
    // the gap from proved comes out of shelved's side, so this is the
    // floor that stops "darker" from sliding into "gone": it stays
    // clearly above the abandoned residue
    const L = (s: GoalStatus): number => {
      const m = nodeStyle(goal(s), true)
      return lightness(m.stroke, m.opacity)
    }
    expect(L('shelved')).toBeGreaterThan(L('dead') + 6)
  })

  it('lets a refuted star glow in no sky', () => {
    expect(nodeStyle(goal('disproved'), true).glow).toBe(false)
    expect(nodeStyle(goal('disproved'), false).glow).toBe(false)
  })

  it('recedes the proved mass while anything is live, and only then', () => {
    const live = nodeStyle(goal('proved'), true)
    const done = nodeStyle(goal('proved'), false)
    expect(lightness(done.fill, done.opacity)).toBeGreaterThan(
      lightness(live.fill, live.opacity) + 25,
    )
    expect(live.glow).toBe(false)
    expect(done.glow).toBe(true)
  })

  it('dulls a proved star that had to fight for it', () => {
    const clean = nodeStyle(goal('proved', { dead_attempts: 0 }), false)
    const fought = nodeStyle(goal('proved', { dead_attempts: 6 }), false)
    expect(lightness(fought.fill, 1)).toBeLessThan(lightness(clean.fill, 1))
  })
})

describe('size hierarchy', () => {
  it('ranks the landmarks the human must see above the supporting work', () => {
    const r = (over: Partial<Goal>) => radius(goal('open', over))
    expect(r({ origin: 'root' })).toBeGreaterThan(r({ human_facing_claim: true }))
    // a claim YOU sign outranks a brick delivered between machines
    expect(r({ human_facing_claim: true })).toBeGreaterThan(r({ is_deliverable: true }))
    expect(r({ is_deliverable: true })).toBeGreaterThan(r({ kind: 'def' }))
    expect(r({ kind: 'def' })).toBeGreaterThan(r({}))
  })
})

describe('line law', () => {
  it('breaks every cross-link and leaves the decomposition solid', () => {
    // a citation and a succeeded route share an ink token AND a bow
    // (a route past 480 curves through the same citePath), so the
    // dash is the only thing standing between them
    expect(CITE_DASH).toMatch(/^[\d.]+ [\d.]+$/)
    expect(ALIAS_DASH).toMatch(/^[\d.]+ [\d.]+$/)
    expect(CITE_DASH).not.toBe(ALIAS_DASH)
  })

  it('gives routes three voices and never paints them with an rgba token', () => {
    // the rgba edge tokens carry their own alpha; stacked under
    // strokeOpacity they net ~2% and the dependency tree vanishes
    const voices = new Set([
      edgeStroke('proposed', 'strategy'),
      edgeStroke('succeeded', 'strategy'),
      edgeStroke('dead', 'strategy'),
    ])
    expect(voices.size).toBe(3)
    for (const v of voices) expect(v).not.toMatch(/edge/)
    expect(edgeStroke('superseded', 'strategy')).toBe(edgeStroke('dead', 'strategy'))
  })

  it('thins the citation weave as it thickens', () => {
    expect(citeInk(5)).toBeGreaterThan(citeInk(50))
    expect(citeInk(50)).toBeGreaterThan(citeInk(200))
  })

  it('keeps a dotted thread readable against a dead route', () => {
    // the pair that used to collide: a dead route (solid, faint) and a
    // citation. They now differ in kind, so this only guards the ink
    // from sinking out of sight
    const dead = lightness(edgeStroke('dead', 'strategy'), 0.4)
    const cite = lightness(edgeStroke('proposed', 'citation'), citeInk(10))
    expect(cite).toBeGreaterThan(dead)
  })
})

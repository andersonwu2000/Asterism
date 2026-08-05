import { describe, expect, it } from 'vitest'
import { scopedRows } from './quota'

const row = (name: string, percent: number, is_active = false) => ({
  name,
  percent,
  resets_at: '2026-08-12T21:59:59+00:00',
  is_active,
})

describe('per-model weekly caps', () => {
  it('shows nothing when the plan reports nothing', () => {
    // there may be stretches with no scoped cap at all — absence is
    // silent, never an empty state
    expect(scopedRows([])).toEqual([])
    expect(scopedRows(undefined)).toEqual([])
    expect(scopedRows(null)).toEqual([])
  })

  it('keeps a reported cap that is not the binding one', () => {
    // filtering on is_active made a real reading (Fable at 8%) vanish
    // on one account and show on another
    const out = scopedRows([row('Fable', 8, false)])
    expect(out.map((s) => s.name)).toEqual(['Fable'])
    expect(out[0].is_active).toBe(false)
  })

  it('names whatever model the account reports', () => {
    // it was Sonnet's cap, it is Fable's now — nothing is hard-coded
    expect(scopedRows([row('Sonnet', 40, true)])[0].name).toBe('Sonnet')
  })

  it('orders binding first, then by name — never by array order', () => {
    const out = scopedRows([row('Zeta', 1), row('Alpha', 2), row('Mid', 3, true)])
    expect(out.map((s) => s.name)).toEqual(['Mid', 'Alpha', 'Zeta'])
  })

  it('drops nameless rows and survives a nonsense percent', () => {
    const out = scopedRows([
      row('  ', 5),
      { ...row('Fable', Number.NaN), percent: Number.NaN },
    ])
    expect(out.map((s) => [s.name, s.percent])).toEqual([['Fable', 0]])
  })

  it('collapses a duplicated name onto the binding reading', () => {
    const out = scopedRows([row('Fable', 8, false), row('Fable', 12, true)])
    expect(out).toHaveLength(1)
    expect(out[0].percent).toBe(12)
  })
})

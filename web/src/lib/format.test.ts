import { describe, expect, it } from 'vitest'
import {
  compactGoalLabel,
  goalCode,
  goalLabel,
  groupCode,
  groupLabel,
} from './format'

describe('stable machine identities', () => {
  it('uses the same goal and group vocabulary as agents', () => {
    expect(goalCode(123)).toBe('g123')
    expect(groupCode(456)).toBe('G456')
  })

  it('keeps the code beside the readable name', () => {
    expect(goalLabel(123, 'finite_cover')).toBe('g123 · finite_cover')
    expect(groupLabel(456, 'compactness track')).toBe('G456 · compactness track')
  })

  it('shortens a sky label without clipping the code agents use', () => {
    expect(compactGoalLabel(12345, 'a_very_long_goal_name', 14)).toBe('g12345 · a_…me')
    expect(compactGoalLabel(12345, 'anything', 5)).toBe('g12345')
  })
})

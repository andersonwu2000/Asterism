import { describe, expect, it } from 'vitest'
import { benchPath } from './bench'

/*
 * Bench is the reversible "stop this task without stopping the run"
 * (owner's ruling). The console owes exactly one thing here: post to
 * the endpoint that matches the direction the reader pressed, at a
 * name the router can carry. Getting the pair backwards would put a
 * task back on the live path from a button that says it takes it off.
 */

describe('benchPath', () => {
  it('names the direction, not the state it came from', () => {
    expect(benchPath('Erdos.p1', true)).toBe('/api/problems/Erdos.p1/bench')
    expect(benchPath('Erdos.p1', false)).toBe('/api/problems/Erdos.p1/unbench')
  })

  it('encodes the task name — a problem name is not a path', () => {
    expect(benchPath('Combinatorics/union closed', true)).toBe(
      '/api/problems/Combinatorics%2Funion%20closed/bench',
    )
  })
})

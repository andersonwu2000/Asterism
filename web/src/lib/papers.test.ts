import { describe, expect, it } from 'vitest'
import { shelfGroups } from './papers'
import type { PaperShelfItem } from './types'

const paper = (id: string, problems: string[]): PaperShelfItem => ({
  id,
  source_name: `${id}.pdf`,
  title: null,
  added_by: 'fetched',
  pages: 1,
  chars: 100,
  original: `${id}.pdf`,
  has_map: false,
  map_stale: false,
  bound: problems.map((p) => ({ problem: p, origin: 'agent' })),
})

describe('arranging the shelf by problem', () => {
  it('groups by problem, sorted, with the unregistered pile last', () => {
    const g = shelfGroups([
      paper('a', ['Topology.slc']),
      paper('b', []),
      paper('c', ['Combinatorics.uc']),
      paper('d', ['Combinatorics.uc']),
    ])
    expect(g.map((x) => [x.problem, x.papers.length])).toEqual([
      ['Combinatorics.uc', 2],
      ['Topology.slc', 1],
      [null, 1],
    ])
  })

  it('a paper serving two problems appears under each', () => {
    const g = shelfGroups([paper('a', ['P.one', 'P.two'])])
    expect(g.map((x) => x.problem)).toEqual(['P.one', 'P.two'])
    expect(g[0].papers[0].id).toBe('a')
    expect(g[1].papers[0].id).toBe('a')
  })

  it('double bindings to one problem stay one row', () => {
    const p = paper('a', ['P.one', 'P.one'])
    const g = shelfGroups([p])
    expect(g).toHaveLength(1)
    expect(g[0].papers).toHaveLength(1)
  })

  it('no unregistered group when everything is bound', () => {
    const g = shelfGroups([paper('a', ['P.one'])])
    expect(g.some((x) => x.problem === null)).toBe(false)
  })
})

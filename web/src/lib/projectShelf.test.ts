import { describe, expect, it } from 'vitest'
import { previewCandidates, visibleProjects } from './projectShelf'
import type { BoardProblem, ProjectCard } from './types'

const project = (name: string, extra: Partial<ProjectCard> = {}): ProjectCard => ({
  name, description: '', problems: 1, running: 0, attention: 0, last_event: null, ...extra,
})

it('samples only nonempty tasks filed on the project, preserving fallbacks', () => {
  const task = (name: string, project: string, total: number) => ({ name, project, goals: { total } }) as BoardProblem
  const rows = [task('OldName.a', 'Renamed', 4), task('OldName.empty', 'Renamed', 0),
    task('OldName.b', 'Renamed', 6), task('Renamed.wrong', 'Elsewhere', 100)]
  expect(previewCandidates(rows, 'Renamed', 0)).toEqual(['OldName.a', 'OldName.b'])
  expect(previewCandidates(rows, 'Renamed', 0.99)).toEqual(['OldName.b', 'OldName.a'])
  expect(previewCandidates(rows, 'Empty', 0.5)).toEqual([])
})

describe('project picker', () => {
  const rows = [project('Topology', { running: 1 }), project('Algebra'),
    project('Combinatorics', { description: 'Union-closed families', attention: 2 })]

  it('keeps a stable alphabetical order without mutating the response', () => {
    expect(visibleProjects(rows, '', 'all').map(p => p.name))
      .toEqual(['Algebra', 'Combinatorics', 'Topology'])
    expect(rows[0].name).toBe('Topology')
  })
  it('searches names and descriptions, ignoring case and surrounding space', () => {
    expect(visibleProjects(rows, ' UNION-CLOSED ', 'all')[0].name).toBe('Combinatorics')
    expect(visibleProjects(rows, 'TOPO', 'all')[0].name).toBe('Topology')
  })
  it('combines the search and the server-reported attention or running counts', () => {
    expect(visibleProjects(rows, '', 'attention').map(p => p.name)).toEqual(['Combinatorics'])
    expect(visibleProjects(rows, '', 'running').map(p => p.name)).toEqual(['Topology'])
    expect(visibleProjects(rows, 'algebra', 'running')).toEqual([])
    expect(visibleProjects([], '', 'all')).toEqual([])
  })
})

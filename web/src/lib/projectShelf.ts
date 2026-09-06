import type { BoardProblem, ProjectCard } from './types'

export type ProjectFilter = 'all' | 'running' | 'attention'

/** Presentation only: liveness and attention come from the API, never
 * from goal counts or timestamps. Polls must not reshuffle the tiles. */
export function visibleProjects(rows: ProjectCard[], query: string, filter: ProjectFilter) {
  const q = query.trim().toLowerCase()
  return rows.filter(p =>
    (filter === 'all' || (filter === 'running' ? p.running > 0 : p.attention > 0)) &&
    `${p.name}\n${p.description}`.toLowerCase().includes(q),
  ).sort((a, b) => a.name.localeCompare(b.name))
}

/** Random starting point, stable thereafter. Keep all nonempty
 * candidates so a task emptied between the two GETs can be skipped. */
export function previewCandidates(rows: BoardProblem[], project: string, sample: number): string[] {
  const names = rows.filter(p => p.project === project && p.goals.total > 0)
    .map(p => p.name).sort()
  const start = Math.min(names.length - 1, Math.max(0, Math.floor(sample * names.length)))
  return names.length ? [...names.slice(start), ...names.slice(0, start)] : []
}

import type { BoardProblem } from './types'

/*
 * The Project shell's address book (human_interface_design.md §1.4).
 *
 * One hash shape for everything inside a Project —
 * `#/p/<project>/<section>[/<task or path…>]` — so a section switch, a
 * task switch and a reload all name the same thing, and a link mailed
 * to someone opens what the sender was looking at.
 *
 * These are the parts with a right answer, so they are here and tested
 * rather than inline in the shell: which section a segment means, which
 * task a section opens on when the address names none, and whether the
 * task column has anything to offer.
 */

export const SECTIONS = ['tasks', 'sky', 'groups', 'engine', 'timeline', 'docs'] as const

export type Section = (typeof SECTIONS)[number]

/** English labels, in the owner's order (§1.4-2). */
export const SECTION_LABEL: Record<Section, string> = {
  tasks: 'Tasks',
  sky: 'Sky',
  groups: 'Groups',
  engine: 'Engine room',
  timeline: 'Timeline',
  docs: 'Documents',
}

/** The sections that show ONE task, and therefore carry its name in the
 * address. `engine` is the odd one out: the machine is a single daemon,
 * whatever it happens to be running, so its room belongs to the whole
 * shelf.
 *
 * `timeline` LEFT this list (2026-09-03): it was here because the only
 * shelf-wide feed available was the RUN's, and on an idle shelf that is
 * some other Project's last run. `GET /api/projects/{p}/events` is the
 * Project's own history, so the section reads whole first and scopes to
 * a task when the address names one — which is what §1.4 asks for (a
 * Project surface whose secondary menu is the task list). */
export const TASK_SECTIONS: Section[] = ['tasks', 'sky', 'groups']

export interface ProjectRoute {
  project: string
  section: Section
  /** the task this address names, for a task section */
  problem: string | null
  /** `…/sky/<task>/g/<id>` — a star named in the address, so a link to
   * one node survives being mailed */
  goal: number | null
  /** everything after the section that is not a task — the documents
   * path, and nothing else today */
  rest: string[]
}

/** `null` when these segments are not a Project address at all. An
 * unknown section resolves to Tasks rather than rendering an empty
 * frame: a stale bookmark should land somewhere real. */
export function parseProjectRoute(segments: string[]): ProjectRoute | null {
  if (segments[0] !== 'p') return null
  const project = segments[1]
  if (!project) return null
  const raw = segments[2] ?? 'tasks'
  const section = (SECTIONS as readonly string[]).includes(raw)
    ? (raw as Section)
    : 'tasks'
  const tail = segments.slice(3)
  if (section === 'docs')
    return { project, section, problem: null, goal: null, rest: tail }
  // every other section may carry a task: the three that REQUIRE one
  // (TASK_SECTIONS) and the two where it is a pin the reader set on a
  // fleet — one shape, so the shell never parses two.
  const goal = tail[1] === 'g' && tail[2] ? Number(tail[2]) : NaN
  return {
    project,
    section,
    problem: tail[0] ?? null,
    goal: Number.isFinite(goal) ? goal : null,
    rest: [],
  }
}

export function projectPath(
  project: string,
  section: Section,
  problem?: string | null,
  goal?: number | null,
): string {
  const base = `/p/${encodeURIComponent(project)}/${section}`
  if (!problem) return base
  const withTask = `${base}/${encodeURIComponent(problem)}`
  return goal === undefined || goal === null ? withTask : `${withTask}/g/${goal}`
}

/** The rows that belong to THIS shelf.
 *
 * `/api/problems?project=` already filters, so this is not a second
 * filter — it is the guard for the window between two addresses, where
 * the shell has walked to a new Project and the poll for it has not
 * answered yet. Reading the previous shelf's rows there rewrote the
 * address to another Project's task (2026-09-03). Membership is the FK
 * (§3.1) and nothing else: a row filed nowhere belongs nowhere. */
export function tasksOf(rows: BoardProblem[], project: string): BoardProblem[] {
  return rows.filter((p) => p.project === project)
}

/** Which task a section opens on when the address names none.
 *
 * Attention order, the same order the shelf itself is read in: what is
 * blocked on the human, then what the engine is working, then whatever
 * moved most recently. Name order is the last resort — deterministic,
 * so a fresh Project does not open on a different task each reload. */
export function defaultTask(rows: BoardProblem[]): string | null {
  if (rows.length === 0) return null
  const rank = (p: BoardProblem): number =>
    p.status === 'awaiting_human' || p.status === 'signoff_pending'
      ? 0
      : p.status === 'stalled'
        ? 1
        : p.status === 'proving' || p.in_flight > 0
          ? 2
          : 3
  const best = [...rows].sort(
    (a, b) =>
      rank(a) - rank(b) ||
      (b.last_event ?? '').localeCompare(a.last_event ?? '') ||
      a.name.localeCompare(b.name),
  )[0]
  return best.name
}

/** The task column is a chooser; with nothing to choose it is chrome
 * describing itself (§1.4: "單任務時不顯示"). */
export function railVisible(rows: BoardProblem[]): boolean {
  return rows.length > 1
}

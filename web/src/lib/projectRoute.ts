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

export const SECTIONS = ['workspace', 'tasks', 'sky', 'groups', 'engine', 'timeline'] as const

export type Section = (typeof SECTIONS)[number]

/** English labels, in the owner's order (§1.4-2). One word each: the
 * menu is read at a glance, and `engine` was "Engine room" until
 * 2026-09-05 — the surface is where the engine is watched, and every
 * sentence in the UI already calls the machine "the engine"; the room
 * was a metaphor spending a second word. The address segment did not
 * change.
 *
 * `workspace` was "Documents" until 2026-09-08 (owner). The section is
 * where a person WRITES — their own files, the papers they shelved, the
 * engine's writing beside them — and "Documents" named the drawer
 * rather than the work. It is also the Project's first page now, so it
 * leads the menu and it is what an address naming no section opens. */
export const SECTION_LABEL: Record<Section, string> = {
  workspace: 'Workspace',
  tasks: 'Tasks',
  sky: 'Sky',
  groups: 'Groups',
  engine: 'Engine',
  timeline: 'Timeline',
}

/** Segments an older address spelt a section with, and what they mean
 * now. `docs` is in bookmarks, chat answers and the Inbox, so it keeps
 * reading — `renamedProjectPath` rewrites it, and the parser below
 * resolves it in the meantime so nothing renders a blank frame while
 * the rewrite lands. */
const RENAMED: Record<string, Section> = { docs: 'workspace' }

/** The canonical address for one minted under an old section name, or
 * null when the address is already canonical.
 *
 * The tail is carried across whole: `#/p/X/docs/user/a.md` names a
 * document, and a redirect that dropped it would land the reader on the
 * section with nothing open — which is exactly what the bookmark was
 * saved to avoid. */
export function renamedProjectPath(segments: string[]): string | null {
  if (segments[0] !== 'p' || !segments[1]) return null
  const to = RENAMED[segments[2] ?? '']
  if (to === undefined) return null
  const tail = segments.slice(3).map(encodeURIComponent)
  return [`/p/${encodeURIComponent(segments[1])}/${to}`, ...tail].join('/')
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
  /** `…/groups/<task>/rev/<id>` — one Programme revision, the same way.
   * A Timeline row already knows which revision it IS; until this
   * existed the only place to send it was the group's history list,
   * where the reader had to find the row again (owner, 2026-09-06).
   * The `revisions` row id, never the rev NUMBER: a killed proposal
   * and the revision that later takes its number are both "rev N". */
  rev: number | null
  /** everything after the section that is not a task — the Workspace's
   * document path, and nothing else today */
  rest: string[]
}

/** `null` when these segments are not a Project address at all. An
 * unknown section resolves to the Project's first page rather than
 * rendering an empty frame: a stale bookmark should land somewhere
 * real, and that is the same page an address naming no section opens. */
export function parseProjectRoute(segments: string[]): ProjectRoute | null {
  if (segments[0] !== 'p') return null
  const project = segments[1]
  if (!project) return null
  const raw = segments[2] ?? SECTIONS[0]
  const section = (SECTIONS as readonly string[]).includes(raw)
    ? (raw as Section)
    : (RENAMED[raw] ?? SECTIONS[0])
  const tail = segments.slice(3)
  if (section === 'workspace')
    return { project, section, problem: null, goal: null, rev: null, rest: tail }
  // every other section may carry a task: the three that REQUIRE one
  // (TASK_SECTIONS) and the two where it is a pin the reader set on a
  // fleet — one shape, so the shell never parses two. After the task,
  // a section may name ONE object of its own: the Sky a star, Groups a
  // revision. Same slot, same guard against a NaN selection.
  const node = tail[1] === 'g' || tail[1] === 'rev' ? Number(tail[2]) : NaN
  const at = Number.isFinite(node) ? node : null
  return {
    project,
    section,
    problem: tail[0] ?? null,
    goal: tail[1] === 'g' ? at : null,
    rev: tail[1] === 'rev' ? at : null,
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

/** One Programme revision's address, or the argument as it stands.
 *
 * Its own function rather than a fifth argument to `projectPath`: a
 * revision is not a star, the two can never both be named, and a
 * caller that had to pass `null` past one to reach the other is a
 * caller that will one day pass it to the wrong one. */
export function programmePath(
  project: string,
  problem: string,
  rev?: number | null,
): string {
  const base = projectPath(project, 'groups', problem)
  return rev === undefined || rev === null ? base : `${base}/rev/${rev}`
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

/** How much of the reader's attention a task has earned. Lower is
 * sooner: the human's own move, then what is stuck, then what is
 * moving, then everything settled. */
function attention(p: BoardProblem): number {
  return p.status === 'awaiting_human' || p.status === 'signoff_pending'
    ? 0
    : p.status === 'stalled'
      ? 1
      : p.status === 'proving' || p.in_flight > 0
        ? 2
        : 3
}

/** THE order the shelf is read in, wherever it is read.
 *
 * The task column, the shelf table and "which task does this section
 * open on" are three readings of one list, and until 2026-09-04 they
 * were three different orders — API order, a private status list, and
 * a third rank inside `defaultTask`. Switching section reshuffled the
 * list under the reader, which says the shelf changed when nothing
 * did. One function, so a change of mind about attention lands on all
 * three at once.
 *
 * Inside a rank: what moved most recently, and a task that has never
 * moved last (an absent `last_event` sorts below any timestamp). Name
 * order is the last resort — deterministic, so a fresh Project does
 * not reshuffle itself on every reload. */
export function shelfOrder(rows: BoardProblem[]): BoardProblem[] {
  return [...rows].sort(
    (a, b) =>
      attention(a) - attention(b) ||
      (b.last_event ?? '').localeCompare(a.last_event ?? '') ||
      a.name.localeCompare(b.name),
  )
}

/** Which task a section opens on when the address names none: the top
 * of the shelf as the shelf itself draws it. */
export function defaultTask(rows: BoardProblem[]): string | null {
  return shelfOrder(rows)[0]?.name ?? null
}

/** The task column is a chooser; with nothing to choose it is chrome
 * describing itself (§1.4: "單任務時不顯示"). */
export function railVisible(rows: BoardProblem[]): boolean {
  return rows.length > 1
}

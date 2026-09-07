import { refKey } from './docShell'
import type { DocRef } from './docShell'

/*
 * The Workspace's open documents (owner, 2026-09-08).
 *
 * The rail is a shelf and the shell shows ONE thing off it, so before
 * this every walk through the rail replaced what you were reading:
 * comparing two files, or writing one while reading another, meant
 * finding the row again. A tab strip is the editor's answer and it is
 * the one asked for — open a file and it takes a tab, click a file that
 * is already open and its tab comes forward.
 *
 * The state is a list plus the key of the one on screen, and the parts
 * with a right answer live here rather than in the screen: which tab a
 * close lands on, what a rename does to a tab pointing at the old path,
 * and what survives a reload. `refKey` is the identity throughout —
 * two tasks may each have a `REPORT.md`, and so may the shelf.
 *
 * A tab is NOT where a draft lives. Unsaved writing is in the
 * module-level store (`lib/docDrafts`), keyed by project and path, and
 * nothing here touches it: closing a tab therefore cannot lose work,
 * and reopening the file shows the draft again exactly as walking the
 * rail always has. That is why closing asks no question.
 */

export interface TabState {
  /** every open document, left to right in the order they opened */
  tabs: DocRef[]
  /** `refKey` of the one on screen, or null when the strip is empty */
  active: string | null
}

export const NO_TABS: TabState = { tabs: [], active: null }

/** What the shell should draw. Derived, never stored twice: an `open`
 * ref kept beside the list is an `open` ref that can disagree with it. */
export function activeRef(state: TabState): DocRef | null {
  return state.tabs.find((r) => refKey(r) === state.active) ?? null
}

/** Where this document sits in the strip, or -1. */
export function tabAt(state: TabState, key: string): number {
  return state.tabs.findIndex((r) => refKey(r) === key)
}

/** Open it, or bring it forward if it is already open.
 *
 * A second click on a row must not mint a second tab of the same file:
 * the strip lists documents, not visits. A new one lands at the END —
 * the strip reads in the order things were opened, and inserting beside
 * the active tab would reorder a list the reader has been building. */
export function openTab(state: TabState, ref: DocRef): TabState {
  const key = refKey(ref)
  if (tabAt(state, key) >= 0) return state.active === key ? state : { ...state, active: key }
  return { tabs: [...state.tabs, ref], active: key }
}

/** Bring one forward. A key the strip does not hold changes nothing —
 * the caller is describing a tab that has already been closed. */
export function activateTab(state: TabState, key: string): TabState {
  if (tabAt(state, key) < 0 || state.active === key) return state
  return { ...state, active: key }
}

/** Close one, and say what is on screen afterwards.
 *
 * Closing the ACTIVE tab lands on its right-hand neighbour, or on the
 * left one when it was last: the reader's eye is already at that end of
 * the strip. Closing any other tab leaves the reading alone — a close
 * is not a move. */
export function closeTab(state: TabState, key: string): TabState {
  const i = tabAt(state, key)
  if (i < 0) return state
  const tabs = state.tabs.filter((_, n) => n !== i)
  if (state.active !== key) return { tabs, active: state.active }
  const next = tabs[i] ?? tabs[i - 1] ?? null
  return { tabs, active: next === null ? null : refKey(next) }
}

/** Close every tab the predicate names — the engine group being pointed
 * at another task closes that task's files, because the rail no longer
 * lists them. The reading lands by the same rule as a single close. */
export function closeTabsWhere(
  state: TabState,
  drop: (ref: DocRef) => boolean,
): TabState {
  let next = state
  for (const ref of state.tabs) if (drop(ref)) next = closeTab(next, refKey(ref))
  return next
}

/** Every tab rewritten by `fn`, with the reading following its own tab.
 *
 * ONE shape for "a document this strip holds is now somewhere else": a
 * rename, a folder moved above it, and the legacy address whose task
 * the screen has only just resolved. Two tabs that map onto one path
 * collapse — a rename can land a file on a name the strip already
 * holds, and two tabs of one document is exactly what `openTab`
 * refuses. */
export function mapTabs(state: TabState, fn: (ref: DocRef) => DocRef): TabState {
  const seen = new Set<string>()
  const tabs: DocRef[] = []
  for (const ref of state.tabs) {
    const next = fn(ref)
    const key = refKey(next)
    if (seen.has(key)) continue
    seen.add(key)
    tabs.push(next)
  }
  const held = activeRef(state)
  const active = held === null ? null : refKey(fn(held))
  return { tabs, active: active !== null && seen.has(active) ? active : null }
}

/** A path (or a whole folder) that moved, applied to one ref. The
 * separator is matched with the prefix, so renaming `user/note` leaves
 * `user/notes.md` alone — the same rule `docDrafts::renameDraft` uses,
 * because a tab and its draft must follow the file together. */
export function movedRef(ref: DocRef, from: string, to: string): DocRef {
  if (ref.kind !== 'doc') return ref
  if (ref.path === from) return { kind: 'doc', path: to }
  if (ref.path.startsWith(`${from}/`))
    return { kind: 'doc', path: to + ref.path.slice(from.length) }
  return ref
}

/** What the tab says: the file's own name. The folder above it is the
 * rail's job and the shell's header says it too — a strip of full paths
 * is a strip where nothing is readable. */
export function tabLabel(ref: DocRef): string {
  return ref.path.split('/').pop() ?? ref.path
}

/** The whole path, for the tab's `title`: a truncated name has to be
 * askable, and two `REPORT.md` from two tasks are told apart here. */
export function tabTitle(ref: DocRef): string {
  return ref.kind === 'task' && ref.task !== null ? `${ref.task}/${ref.path}` : ref.path
}

/* -- remembered, per Project ---------------------------------------- */

/** Per Project, in this browser — the same pattern as the rail's fold
 * keys (`asterism.docRail.<group>`). What is open is a posture the
 * reader built up over a session's work, and losing it to a reload is
 * losing the session's shape. */
export const tabsKey = (project: string): string => `asterism.workspace.tabs.${project}`

/** Is this something the strip can hold? A stored blob is data from an
 * older build or a hand-edited store, never a promise — so every field
 * is checked, and anything unreadable is dropped rather than opened as
 * a document with no path. */
function readRef(v: unknown): DocRef | null {
  if (typeof v !== 'object' || v === null) return null
  const r = v as Record<string, unknown>
  if (typeof r.path !== 'string' || r.path === '') return null
  if (r.kind === 'doc') return { kind: 'doc', path: r.path }
  if (r.kind === 'task' && (typeof r.task === 'string' || r.task === null))
    return { kind: 'task', task: r.task as string | null, path: r.path }
  return null
}

/** What this Project's strip held last. Every access is guarded: a
 * private window, cleared site data or a browser set to refuse storage
 * all throw on the ACCESSOR, and the tab strip is not worth a page that
 * fails to render (`docShell::readSplit` makes the same ruling). */
export function readTabs(project: string): TabState {
  try {
    const raw = localStorage.getItem(tabsKey(project))
    if (raw === null) return NO_TABS
    const held = JSON.parse(raw) as { tabs?: unknown; active?: unknown }
    if (!Array.isArray(held?.tabs)) return NO_TABS
    const seen = new Set<string>()
    const tabs: DocRef[] = []
    for (const v of held.tabs) {
      const ref = readRef(v)
      if (ref === null || seen.has(refKey(ref))) continue
      seen.add(refKey(ref))
      tabs.push(ref)
    }
    if (tabs.length === 0) return NO_TABS
    // an active key naming no tab is not a reading — the leftmost tab
    // is, and an empty strip is the only honest "nothing open"
    const active =
      typeof held.active === 'string' && seen.has(held.active)
        ? held.active
        : refKey(tabs[0])
    return { tabs, active }
  } catch {
    return NO_TABS
  }
}

export function writeTabs(project: string, state: TabState): void {
  try {
    localStorage.setItem(tabsKey(project), JSON.stringify(state))
  } catch {
    /* the reading is the point; remembering it is the courtesy */
  }
}

/* -- the keyboard on the strip -------------------------------------- */

/** Where the arrows put the FOCUS (not the reading — activation is
 * manual here, the way the rail's arrows walk rows without opening
 * them; Enter reads, and Delete closes whatever the focus is on).
 * Wrapping, like the rail's `focusRow`. Anything this does not own
 * returns null, so the handler leaves the event alone. */
export function tabStep(at: number, key: string, count: number): number | null {
  if (count === 0) return null
  if (key === 'ArrowRight') return (at + 1) % count
  if (key === 'ArrowLeft') return (at - 1 + count) % count
  if (key === 'Home') return 0
  if (key === 'End') return count - 1
  return null
}

import { useSyncExternalStore } from 'react'

/*
 * Unsaved writing on the Project's documents (docs_tab_spec.md §B5).
 *
 * A MODULE-LEVEL store, like `lib/focus` and `lib/goalFocus`: a draft
 * has to survive walking the rail, folding a group and switching
 * section, so it cannot live in the component that happens to be
 * drawing the editor. Leaving a file must never destroy work.
 *
 * A draft is stored ONLY while it differs from the disk copy — the
 * screen drops it the moment the two agree (`isDirty` is the law that
 * decides). That is what makes "which documents hold unsaved writing"
 * a question about the store's keys rather than a comparison this
 * module cannot make: it does not hold the disk copy of anything but
 * the open document.
 */

export interface Draft {
  text: string
  /** the sha1 the disk copy carried when this draft was started, so a
   * PUT can refuse to overwrite someone else's newer bytes (§A2).
   * null = there was no base (a file created here, or a re-save the
   * person chose to force). */
  baseEtag: string | null
}

/** One key, two facts. NUL because it cannot occur in either half — a
 * `:` would let a Project named `A` and a path `B:C` collide with a
 * Project `A:B` and a path `C`. */
const keyOf = (project: string, path: string): string => `${project}\u0000${path}`

const drafts = new Map<string, Draft>()
const listeners = new Set<() => void>()

/** Bumped on every change. `useSyncExternalStore` compares snapshots by
 * identity, so the per-Project view below is rebuilt only when this
 * moves — a component reading it does not get a new object (and a new
 * render) on someone else's keystroke. */
let version = 0
const views = new Map<string, { at: number; map: ReadonlyMap<string, Draft> }>()

function changed(): void {
  version += 1
  for (const cb of listeners) cb()
}

export function setDraft(
  project: string,
  path: string,
  text: string,
  baseEtag: string | null,
): void {
  drafts.set(keyOf(project, path), { text, baseEtag })
  changed()
}

export function getDraft(project: string, path: string): Draft | undefined {
  return drafts.get(keyOf(project, path))
}

export function dropDraft(project: string, path: string): void {
  if (drafts.delete(keyOf(project, path))) changed()
}

/** Follow a rename or a move.
 *
 * `from` may be a FOLDER, in which case every draft under it is
 * re-keyed — the whole subtree moved, and the writing inside it moved
 * with the files. The prefix is matched with its separator, so
 * renaming `user/note` leaves `user/notes.md` alone. */
export function renameDraft(project: string, from: string, to: string): void {
  const prefix = `${from}/`
  const moves: [string, string][] = []
  for (const key of drafts.keys()) {
    const head = `${project}\u0000`
    if (!key.startsWith(head)) continue
    const path = key.slice(head.length)
    if (path === from) moves.push([path, to])
    else if (path.startsWith(prefix)) moves.push([path, to + path.slice(from.length)])
  }
  if (moves.length === 0) return
  for (const [oldPath, newPath] of moves) {
    const draft = drafts.get(keyOf(project, oldPath))
    drafts.delete(keyOf(project, oldPath))
    if (draft !== undefined) drafts.set(keyOf(project, newPath), draft)
  }
  changed()
}

/** Every document in this Project still holding unsaved writing.
 * Sorted, so a header counting them does not reorder itself. */
export function dirtyPaths(project: string): string[] {
  const head = `${project}\u0000`
  return [...drafts.keys()]
    .filter((k) => k.startsWith(head))
    .map((k) => k.slice(head.length))
    .sort()
}

/** This Project's drafts, reactive. The map is rebuilt only when the
 * store changes, so it is safe as a `useSyncExternalStore` snapshot. */
export function useDrafts(project: string): ReadonlyMap<string, Draft> {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => snapshot(project),
    () => snapshot(project),
  )
}

function snapshot(project: string): ReadonlyMap<string, Draft> {
  const held = views.get(project)
  if (held !== undefined && held.at === version) return held.map
  const head = `${project}\u0000`
  const map = new Map<string, Draft>()
  for (const [k, v] of drafts) if (k.startsWith(head)) map.set(k.slice(head.length), v)
  views.set(project, { at: version, map })
  return map
}

/** Is there work here that the disk does not have?
 *
 * Typing and then undoing is not unsaved work, so a draft that matches
 * the disk copy exactly is not dirty. A draft with no disk copy in hand
 * (the read has not landed, or the file was removed underneath) IS
 * dirty — the writing exists either way, and the honest answer to "may
 * I close this?" is no. */
export function isDirty(draft: Draft | undefined | null, diskText?: string | null): boolean {
  if (!draft) return false
  if (diskText === undefined || diskText === null) return true
  return draft.text !== diskText
}

/** The `beforeunload` handler's body.
 *
 * App.tsx refuses this prompt for a live RUN (owner, 2026-07-18): the
 * browser's generic dialog implies unsaved work that does not exist,
 * and closing the page does not stop the engine. Unsaved writing in an
 * editor is the case that comment leaves open — here the dialog's
 * implication is exactly true.
 *
 * A body rather than a factory, so the screen installs ONE listener and
 * reads the current count through a ref: re-registering on every
 * keystroke is how a guard ends up missing during the frame it is being
 * replaced. */
export function unsavedGuard(
  dirtyCount: number,
  e: { preventDefault(): void; returnValue?: unknown },
): string | undefined {
  if (dirtyCount <= 0) return undefined
  // the modern channel and the legacy one. Browsers show their own
  // wording, so this sentence is never read by a person — but an EMPTY
  // string is how some of them spell "no, go ahead", so it has to be a
  // real one.
  const say = `${dirtyCount} document${dirtyCount === 1 ? '' : 's'} still hold unsaved changes.`
  e.preventDefault()
  e.returnValue = say
  return say
}

import { useEffect, useSyncExternalStore } from 'react'

/*
 * What the reader has OPEN, published by the screen that is drawing it
 * and read by the Assistant panel (human_interface_design.md §1.4-2:
 * the panel receives the star that was clicked, the group being read,
 * the document under the cursor — "這是它勝過 Ask 的關鍵").
 *
 * A module-level store rather than context, for the same reason
 * `lib/goalFocus` is one: the panel and the section live in different
 * subtrees, and the hash router owns everything between them.
 *
 * The publisher REPLACES the store. Exactly one section is mounted at
 * a time inside a Project, so "what is open" has one author; merging
 * instead would leave a star selected on a screen the reader left, and
 * the panel would prime its session on it.
 */

export interface ScreenFocus {
  /** the task, when the screen knows better than the address does */
  problem?: string | null
  goal_id?: number | null
  group_id?: number | null
  /** relative to the Project's docs root, e.g. `user/notes.md` */
  doc_path?: string | null
}

let current: ScreenFocus = {}
const listeners = new Set<() => void>()

function emit(next: ScreenFocus): void {
  current = next
  for (const cb of listeners) cb()
}

export function screenFocus(): ScreenFocus {
  return current
}

/** Publish this screen's focus for as long as it is mounted. */
export function usePublishFocus(focus: ScreenFocus): void {
  // the object identity changes every render; the CONTENT is what the
  // panel is told about
  const key = JSON.stringify(focus)
  useEffect(() => {
    emit(JSON.parse(key) as ScreenFocus)
    return () => emit({})
  }, [key])
}

export function useScreenFocus(): ScreenFocus {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    screenFocus,
    screenFocus,
  )
}

/** The `focus` object the chat endpoint takes (`serve/chat.py`'s
 * ChatBody): one or more of problem / group_id / goal_id / doc_path,
 * each contributing its own section to the context block.
 *
 * `null` when nothing is open — the picker page asks about no task, and
 * a body carrying empty keys would prime the session on nothing.
 */
export function focusBody(
  routeProblem: string | null,
  screen: ScreenFocus,
): Record<string, unknown> | null {
  const out: Record<string, unknown> = {}
  const problem = screen.problem ?? routeProblem
  if (problem) out.problem = problem
  // in the order serve lays their sections out (chat.py FOCUS_KINDS)
  if (typeof screen.group_id === 'number') out.group_id = screen.group_id
  if (typeof screen.goal_id === 'number') out.goal_id = screen.goal_id
  if (screen.doc_path) out.doc_path = screen.doc_path
  return Object.keys(out).length === 0 ? null : out
}

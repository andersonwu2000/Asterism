import { useSyncExternalStore } from 'react'
import type { IntentData } from './types'

export type IntentFields = Pick<IntentData, 'charter' | 'word'> & {
  settings: Pick<IntentData['settings'], 'forbidden_lemmas'>
}
export type IntentPatch = Partial<IntentFields>
interface IntentDraft { patch: IntentPatch; saving: boolean }
const empty: IntentDraft = { patch: {}, saving: false }
const drafts = new Map<string, IntentDraft>()
const listeners = new Set<() => void>()
const saveListeners = new Set<(problem: string, submitted: IntentPatch) => void>()
export function onIntentSaved(listener: (problem: string, submitted: IntentPatch) => void): () => void {
  saveListeners.add(listener)
  return () => { saveListeners.delete(listener) }
}
const read = (problem: string): IntentDraft => drafts.get(problem) ?? empty
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
export const intentDraftCount = (): number => drafts.size

export function discardIntentDraft(problem: string) {
  publish(problem, empty)
}

function publish(problem: string, draft: IntentDraft) {
  if (!draft.saving && Object.keys(draft.patch).length === 0) drafts.delete(problem)
  else drafts.set(problem, draft)
  for (const listener of listeners) listener()
}

/** Only fields the person changed survive navigation. A fresh read still
 * supplies the other fields, including the engine's amendment lock. */
export function setIntentField<K extends keyof IntentFields>(
  problem: string, field: K, value: IntentFields[K], baseline: IntentFields[K],
) {
  const current = read(problem)
  const patch = { ...current.patch }
  // An undo during a save is writing against the incoming disk copy,
  // even when it agrees with the old copy still on screen.
  if (!current.saving && same(value, baseline)) delete patch[field]
  else patch[field] = value
  publish(problem, { ...current, patch })
}

export function beginIntentSave(problem: string): boolean {
  const current = read(problem)
  if (current.saving || Object.keys(current.patch).length === 0) return false
  publish(problem, { ...current, saving: true })
  return true
}

export function finishIntentSave(problem: string, submitted?: IntentPatch) {
  const patch = { ...read(problem).patch }
  if (submitted) {
    for (const field of Object.keys(submitted) as (keyof IntentFields)[]) {
      if (same(patch[field], submitted[field])) delete patch[field]
    }
    for (const listener of saveListeners) listener(problem, submitted)
  }
  publish(problem, { patch, saving: false })
}

export function useIntentDraft(problem: string): IntentDraft {
  return useSyncExternalStore(
    listener => { listeners.add(listener); return () => listeners.delete(listener) },
    () => read(problem),
    () => read(problem),
  )
}

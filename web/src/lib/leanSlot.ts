import { useSyncExternalStore } from 'react'

/*
 * The reader's Lean runs on ONE reserved interactive gateway slot. This
 * coordinates it so only the editor surface the user is actively in
 * holds it — probes and the New page, across every tab/window of this
 * browser. Focusing a surface claims the slot; a BroadcastChannel tells
 * the other tabs/windows to let go (the gateway's own last-register-wins
 * eviction is the cross-browser fallback). Without this, every open
 * surface claimed the single slot at once and they evicted each other in
 * a loop — which wedged multiple tabs on a permanent "checking…".
 */

let activeId: string | null = null
const listeners = new Set<() => void>()

const bc =
  typeof BroadcastChannel !== 'undefined'
    ? new BroadcastChannel('asterism-lean-slot')
    : null

function set(id: string | null) {
  if (activeId === id) return
  activeId = id
  listeners.forEach((l) => l())
}

if (bc) {
  bc.onmessage = (e: MessageEvent) => {
    // another tab/window took the slot — drop ours so it disconnects
    if (e.data && e.data.type === 'claim') set(null)
  }
}

/** This surface is now the active editor — claim the slot browser-wide. */
export function claimLeanSlot(id: string) {
  set(id)
  if (bc) bc.postMessage({ type: 'claim' })
}

/** Give up the slot if we hold it (surface unmounted / closed). */
export function releaseLeanSlot(id: string) {
  if (activeId === id) set(null)
}

/** Reactive: is `id` the surface that currently holds the slot? */
export function useLeanSlotActive(id: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => activeId === id,
  )
}

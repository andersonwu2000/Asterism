import { useLayoutEffect, useRef, useState } from 'react'
import { docKind, refKey } from '../lib/docShell'
import type { DocRef } from '../lib/docShell'
import { tabLabel, tabStep, tabTitle } from '../lib/docTabs'
import { KindGlyph } from './glyphs'

/*
 * The strip of open documents, above the shell (owner, 2026-09-08).
 *
 * The rail chooses; this says what is already chosen. Everything it
 * decides — which tab a close lands on, what a rename does to one, what
 * survives a reload — is in `lib/docTabs` and tested there; this file
 * is the drawing and the keys.
 *
 * Achromatic, like the rest: the reading tab is INK on the surface
 * plate and the rest are dim, which is the console's one way of saying
 * "this is the one you are looking at" (the task column and the section
 * menu say it the same way). Radius is the control rung — a tab is a
 * nav item. No shadow: a lifted tab would say the strip floats over the
 * document, and it does not.
 *
 * Keys walk the rail's grammar (DESIGN.md), so ArrowLeft/Right move the
 * FOCUS and Enter reads — activation is manual, which is what makes
 * Delete meaningful: it closes the tab the focus is on, which may not be
 * the one being read.
 */

export default function DocTabs({
  tabs,
  active,
  dirty,
  onActivate,
  onClose,
  onEmptyClose,
}: {
  tabs: DocRef[]
  /** `refKey` of the document on screen */
  active: string | null
  /** root-relative paths holding unsaved writing (`lib/docDrafts`) */
  dirty: ReadonlySet<string>
  onActivate: (key: string) => void
  onClose: (key: string) => void
  onEmptyClose: () => void
}) {
  const [focusAt, setFocusAt] = useState(0)
  const stripRef = useRef<HTMLDivElement | null>(null)
  const focusAfterClose = useRef<number | null>(null)

  /* The focus follows the reading when the reading is set from
   * somewhere else — the rail, an address, a tab closing under the
   * cursor. Without this, the roving index outlives the tab it named
   * and Delete closes a neighbour. */
  useLayoutEffect(() => {
    const closedAt = focusAfterClose.current
    focusAfterClose.current = null
    if (closedAt !== null && tabs.length === 0) {
      onEmptyClose()
      return
    }
    if (closedAt !== null && tabs.length > 0) {
      const i = Math.min(closedAt, tabs.length - 1)
      setFocusAt(i)
      stripRef.current?.querySelector<HTMLElement>(`[data-tab-at="${i}"]`)?.focus()
      return
    }
    const i = tabs.findIndex((r) => refKey(r) === active)
    if (i >= 0) setFocusAt(i)
    else setFocusAt((at) => Math.min(at, Math.max(0, tabs.length - 1)))
  }, [tabs, active, onEmptyClose])

  // nothing open is not an empty strip: the shell below says so in
  // words, and a bar with no tabs in it is chrome describing itself
  if (tabs.length === 0) return null

  const focus = (i: number) => {
    setFocusAt(i)
    stripRef.current?.querySelector<HTMLElement>(`[data-tab-at="${i}"]`)?.focus()
  }
  const close = (key: string, i: number) => {
    focusAfterClose.current = i
    onClose(key)
  }

  return (
    <div
      ref={stripRef}
      role="tablist"
      aria-label="open documents"
      data-doc-tabs
      /* one line, never two: a strip that wraps moves the document
         under it every time a file is opened */
      className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-edge px-2 py-1"
    >
      {tabs.map((ref, i) => {
        const key = refKey(ref)
        const on = key === active
        const label = tabLabel(ref)
        const held = ref.kind === 'doc' && dirty.has(ref.path)
        return (
          // presentational wrapper: a tablist owns TABS, and the close
          // affordance is a button of its own rather than a control
          // nested inside one
          <span
            key={key}
            role="presentation"
            className={`flex max-w-52 shrink-0 items-center gap-1.5 rounded-lg px-2 py-1 transition-colors ${
              on ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:bg-surface-2/60 hover:text-ink'
            }`}
          >
            <button
              data-tab-at={i}
              role="tab"
              aria-selected={on}
              tabIndex={i === focusAt ? 0 : -1}
              title={tabTitle(ref)}
              className="flex min-w-0 cursor-pointer items-center gap-1.5 font-mono text-[11px]"
              onFocus={() => setFocusAt(i)}
              onClick={() => onActivate(key)}
              onKeyDown={(e) => {
                const step = tabStep(i, e.key, tabs.length)
                if (step !== null) {
                  e.preventDefault()
                  focus(step)
                } else if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onActivate(key)
                } else if (e.key === 'Delete' || e.key === 'Backspace') {
                  // the draft store outlives the tab (`lib/docTabs`), so
                  // closing asks nothing and loses nothing
                  e.preventDefault()
                  close(key, i)
                }
              }}
            >
              <span className={on ? 'text-ink-dim' : 'text-ink-faint'} aria-hidden>
                <KindGlyph kind={docKind(ref.path)} />
              </span>
              <span className="truncate">{label}</span>
            </button>
            {held && (
              /* the rail's own mark for unsaved writing, at the same
                 ink — one fact, one drawing */
              <span className="shrink-0 text-star" title="unsaved changes on this document">
                ·
              </span>
            )}
            <button
              tabIndex={-1}
              aria-label={`close ${label}`}
              title="close (Delete)"
              className="shrink-0 cursor-pointer text-[13px] leading-none text-ink-faint transition-colors hover:text-ink"
              onClick={() => close(key, i)}
            >
              ×
            </button>
          </span>
        )
      })}
    </div>
  )
}

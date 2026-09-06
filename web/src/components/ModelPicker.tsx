import { useEffect, useMemo, useRef, useState } from 'react'
import { pickerRows } from '../lib/models'
import type { PickerRow } from '../lib/models'
import type { ModelGroup } from '../lib/types'

/*
 * Which model answers — read as the hierarchy it is.
 *
 * The offer is two levels deep: a machine has BACKENDS, and each
 * backend ships models. A flat list of slugs makes the reader carry
 * that structure in their head, and a native `<optgroup>` hands the
 * drawing of it to whichever browser is open — the owner's read was
 * that the grouping did not exist (2026-09-06). So the two levels are
 * drawn: a provider header in the console's own header voice, its
 * models indented under it.
 *
 * The caveats ride the HEADER, once. "not installed" and "list not
 * live" are true of a backend, not of any one model; on every row they
 * would be one fact drawn as many times as the vendor ships tiers
 * (DESIGN.md: never draw the same fact twice). `lib/models.pickerRows`
 * owns that rule and is where it is tested.
 *
 * The menu is a menu — anchored to its trigger, not a floating window
 * over the page (DESIGN.md floats a task of its own; choosing from a
 * short list beside the control that shows it is not one). Keys walk
 * the same grammar as the pointer: ↑↓ walk the models, Enter takes
 * one, Escape closes, and the open menu lands on what is seated.
 */

export default function ModelPicker({
  groups,
  value,
  onChange,
  className = '',
  title,
  label = 'model',
  disabled = false,
}: {
  groups: ModelGroup[]
  value: string
  onChange: (model: string) => void
  className?: string
  title?: string
  /** what this picker seats — the trigger's accessible name */
  label?: string
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [at, setAt] = useState(0)
  const boxRef = useRef<HTMLDivElement | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)

  const rows = useMemo(() => pickerRows(groups, value), [groups, value])
  const models = useMemo(
    () => rows.flatMap((r, i) => (r.kind === 'model' ? [i] : [])),
    [rows],
  )

  // the menu opens ON the seated model, not at the top: the reader is
  // usually confirming what is there, or stepping one off it
  useEffect(() => {
    if (!open) return
    const here = rows.findIndex((r) => r.kind === 'model' && r.model === value)
    setAt(here < 0 ? (models[0] ?? 0) : here)
  }, [open, rows, models, value])

  useEffect(() => {
    if (!open) return
    listRef.current?.querySelector<HTMLElement>(`[data-at="${at}"]`)?.focus()
  }, [open, at])

  // a click anywhere else is a dismissal, not a choice
  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', away)
    return () => window.removeEventListener('mousedown', away)
  }, [open])

  const step = (d: number) => {
    if (models.length === 0) return
    const here = models.indexOf(at)
    const next = here < 0 ? 0 : (here + d + models.length) % models.length
    setAt(models[next])
  }

  const take = (row: PickerRow) => {
    if (row.kind !== 'model') return
    onChange(row.model)
    setOpen(false)
  }

  return (
    <div ref={boxRef} className={`relative ${className}`}>
      <button
        type="button"
        disabled={disabled}
        className="flex w-full cursor-pointer items-center gap-1 truncate rounded-lg border border-edge bg-surface py-1 pr-2 pl-2 font-mono text-xs whitespace-nowrap text-ink transition-colors hover:border-edge-strong focus:border-ink-faint focus:outline-none disabled:cursor-default disabled:text-ink-faint"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
        title={title}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setOpen(true)
          }
        }}
      >
        <span className="min-w-0 flex-1 truncate text-left">{value}</span>
        <span className="shrink-0 text-[8px] text-ink-faint" aria-hidden>
          ▼
        </span>
      </button>
      {open && (
        <div
          ref={listRef}
          role="listbox"
          aria-label={`${label} choices`}
          data-model-menu
          // the picker's own rung of the radius ladder: a 10px menu
          // holding 6px rows, exactly as the native one is styled in
          // index.css — the two must not read as different objects
          className="absolute right-0 z-30 mt-1 max-h-72 min-w-full overflow-x-hidden overflow-y-auto rounded-[10px] border border-edge-strong bg-surface-2 p-1 shadow-none"
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.stopPropagation()
              setOpen(false)
            } else if (e.key === 'ArrowDown') {
              e.preventDefault()
              step(1)
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              step(-1)
            }
          }}
        >
          {rows.length === 0 && (
            <div className="px-2 py-1.5 text-[11px] text-ink-faint">
              no backend on this machine offers a model
            </div>
          )}
          {rows.map((r, i) =>
            r.kind === 'header' ? (
              <div
                key={`h-${r.provider}-${i}`}
                data-provider-header={r.provider}
                className="px-2 pt-2 pb-0.5 text-[10px] font-medium tracking-widest text-ink-faint/70 uppercase first:pt-0.5"
              >
                {r.provider}
                {r.note}
              </div>
            ) : (
              <button
                key={`m-${r.provider}-${r.model}`}
                type="button"
                role="option"
                data-at={i}
                data-model={r.model}
                aria-selected={r.model === value}
                tabIndex={at === i ? 0 : -1}
                // indented UNDER its header: the hierarchy is the
                // reading, not a label the reader has to hold
                className={`block w-full cursor-pointer truncate rounded-md py-1 pr-2 pl-4 text-left font-mono text-xs transition-colors hover:bg-surface-3 focus:bg-surface-3 focus:outline-none ${
                  r.model === value ? 'text-star' : 'text-ink'
                }`}
                onClick={() => take(r)}
                onFocus={() => setAt(i)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    take(r)
                  }
                }}
              >
                {r.model}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  )
}

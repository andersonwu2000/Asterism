import { useEffect, useRef } from 'react'

/*
 * The question, as the transcript keeps it (assistant_redesign
 * _2026-09-06 §1): a quiet card. Clicking it SELECTS it, and the act
 * that belongs to it appears under it — DESIGN.md 2026-09-04, the
 * Workspace rail's grammar: an act lives on the thing's row, never on
 * hover and never a second time in the header.
 *
 * `edit & re-ask` turns the card into a textarea in place. Sending it
 * truncates the transcript at this turn on BOTH sides — the panel says
 * so before the reader commits.
 */

export function UserTurn({
  text,
  selected,
  editing,
  draft,
  canEdit,
  onSelect,
  onEdit,
  onDraft,
  onSubmit,
  onCancel,
}: {
  text: string
  selected: boolean
  editing: boolean
  draft: string
  /** false while a turn is streaming — one question at a time */
  canEdit: boolean
  onSelect: () => void
  onEdit: () => void
  onDraft: (v: string) => void
  onSubmit: () => void
  onCancel: () => void
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const wasEditing = useRef(false)
  useEffect(() => {
    const closing = wasEditing.current && !editing
    wasEditing.current = editing
    if (closing) rootRef.current?.querySelector<HTMLButtonElement>('button[data-user-question]')?.focus()
    if (editing) {
      const el = ref.current
      if (!el) return
      el.focus()
      el.selectionStart = el.value.length
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 220)}px`
    }
  }, [editing])

  if (editing)
    return (
      <div ref={rootRef} className="mt-5 first:mt-0">
        <div className="rounded-xl border border-edge bg-surface-2 px-2 py-1.5">
          <textarea
            ref={ref}
            value={draft}
            aria-label="Edit question"
            rows={2}
            className="max-h-56 w-full resize-none bg-transparent px-1 py-0.5 text-[13px] text-ink focus:outline-none"
            onInput={(e) => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = `${Math.min(el.scrollHeight, 220)}px`
            }}
            onChange={(e) => onDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.stopPropagation()
                onCancel()
              } else if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                if (canEdit && draft.trim() !== '') onSubmit()
              }
            }}
          />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2 pl-1 text-[11px] text-ink-faint">
          <button
            className="cursor-pointer transition-colors hover:text-ink"
            onClick={onSubmit}
            disabled={!canEdit || draft.trim() === ''}
            title="everything after this question is dropped, here and on the engine"
          >
            re-ask
          </button>
          <span aria-hidden>·</span>
          <button className="cursor-pointer transition-colors hover:text-ink" onClick={onCancel}>
            cancel
          </button>
          <span className="ml-auto">later turns are dropped</span>
        </div>
      </div>
    )

  const Card = canEdit ? 'button' : 'div'
  return (
    <div ref={rootRef} className="mt-5 first:mt-0">
      <Card
        data-user-question
        aria-expanded={canEdit ? selected : undefined}
        className={`w-full cursor-text rounded-xl px-3 py-2 text-left text-[13px] whitespace-pre-wrap transition-colors ${
          selected ? 'bg-surface-3 text-ink' : 'bg-surface-2 text-ink'
        }`}
        onClick={canEdit ? onSelect : undefined}
      >
        {text}
      </Card>
      {selected && canEdit && (
        <div className="mt-1 pl-1 text-[11px] text-ink-faint">
          <button className="cursor-pointer transition-colors hover:text-ink" onClick={onEdit}>
            edit &amp; re-ask
          </button>
        </div>
      )}
    </div>
  )
}

export default UserTurn

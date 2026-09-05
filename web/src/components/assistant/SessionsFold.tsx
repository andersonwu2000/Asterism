import { useEffect, useRef, useState } from 'react'
import { relTime } from '../../lib/format'
import type { ChatSessionSummary } from '../../lib/types'

/*
 * The conversations on this Project's shelf (assistant_redesign
 * _2026-09-06 §1, §2). It opens IN PLACE under the header — DESIGN.md:
 * do not float what the page can simply say.
 *
 * The current conversation carries the dot; the SELECTED row carries
 * the acts, and only that row (DESIGN.md 2026-09-04, the Documents
 * rail). Delete confirms in place, in the words of what happens. The
 * keys walk the same grammar as the pointer: ↑↓ Enter F2 Delete Esc.
 */

export function SessionsFold({
  sessions,
  currentId,
  streaming,
  note,
  onOpen,
  onNew,
  onRename,
  onDelete,
  onClose,
}: {
  sessions: ChatSessionSummary[]
  currentId: string | null
  /** an answer is being written — the conversation it is on cannot go */
  streaming: boolean
  /** an API refusal, rendered at the row it concerns */
  note: { id: string | null; text: string } | null
  onOpen: (id: string) => void
  onNew: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  onClose: () => void
}) {
  const at0 = sessions.findIndex((s) => s.id === currentId)
  const [sel, setSel] = useState(at0 < 0 ? 0 : at0 + 1)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [confirming, setConfirming] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const renameRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (renaming !== null) renameRef.current?.focus()
  }, [renaming])
  // the fold opens on the conversation being read
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-at="${sel}"]`)?.focus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const focusAt = (i: number) => {
    const n = sessions.length + 1
    const to = ((i % n) + n) % n
    setSel(to)
    listRef.current?.querySelector<HTMLElement>(`[data-at="${to}"]`)?.focus()
  }

  const startRename = (s: ChatSessionSummary) => {
    setConfirming(null)
    setDraft(s.title)
    setRenaming(s.id)
  }

  const onKey = (e: React.KeyboardEvent, i: number) => {
    const s = i === 0 ? null : sessions[i - 1]
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      focusAt(i + 1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      focusAt(i - 1)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (s === null) onNew()
      else onOpen(s.id)
    } else if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
    } else if (s !== null && e.key === 'F2') {
      e.preventDefault()
      startRename(s)
    } else if (s !== null && e.key === 'Delete') {
      e.preventDefault()
      setConfirming(s.id)
    }
  }

  const rowNote = (id: string | null) =>
    note !== null && note.id === id ? (
      <div className="px-3 pb-1 text-[11px] text-warn">{note.text}</div>
    ) : null

  return (
    <div ref={listRef} className="border-b border-edge py-1" aria-label="conversation list">
      <button
        data-at={0}
        tabIndex={sel === 0 ? 0 : -1}
        className={`flex w-full cursor-pointer items-center px-3 py-1.5 text-left text-[12px] transition-colors focus:outline-none ${
          sel === 0 ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:bg-surface-2 hover:text-ink'
        }`}
        onClick={() => {
          setSel(0)
          onNew()
        }}
        onKeyDown={(e) => onKey(e, 0)}
        onFocus={() => setSel(0)}
      >
        + new conversation
      </button>
      {rowNote(null)}
      {sessions.map((s, i) => {
        const at = i + 1
        const on = sel === at
        const current = s.id === currentId
        return (
          <div key={s.id}>
            {renaming === s.id ? (
              <div className="px-3 py-1">
                <input
                  ref={renameRef}
                  value={draft}
                  className="w-full rounded-md border border-edge bg-bg px-1.5 py-0.5 text-[12px] text-ink focus:border-ink-faint focus:outline-none"
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      onRename(s.id, draft.trim())
                      setRenaming(null)
                    } else if (e.key === 'Escape') {
                      e.stopPropagation()
                      setRenaming(null)
                    }
                  }}
                  onBlur={() => setRenaming(null)}
                  title="empty restores the title derived from the first question"
                />
              </div>
            ) : (
              <button
                data-at={at}
                tabIndex={on ? 0 : -1}
                aria-current={current ? 'true' : undefined}
                className={`flex w-full cursor-pointer items-baseline gap-2 px-3 py-1.5 text-left transition-colors focus:outline-none ${
                  on ? 'bg-surface-2' : 'hover:bg-surface-2'
                }`}
                onClick={() => {
                  setSel(at)
                  onOpen(s.id)
                }}
                onKeyDown={(e) => onKey(e, at)}
                onFocus={() => setSel(at)}
              >
                <span className="flex w-2 shrink-0 justify-center">
                  {current && <span className="h-1.5 w-1.5 rounded-full bg-ink" aria-hidden />}
                </span>
                <span
                  className={`min-w-0 flex-1 truncate text-[12px] ${current ? 'text-ink' : 'text-ink-dim'}`}
                >
                  {s.title || 'new conversation'}
                </span>
                <span className="tnum shrink-0 text-[10px] text-ink-faint">
                  {s.turns} turn{s.turns === 1 ? '' : 's'} · {relTime(s.updated_at)}
                </span>
              </button>
            )}
            {on && renaming !== s.id && (
              <div className="flex items-center gap-2 px-3 pb-1 pl-[22px] text-[11px] text-ink-faint">
                <button
                  className="cursor-pointer transition-colors hover:text-ink"
                  onClick={() => startRename(s)}
                  title="F2"
                >
                  rename
                </button>
                <span aria-hidden>·</span>
                {confirming === s.id ? (
                  <button
                    className="cursor-pointer text-warn transition-colors hover:text-ink"
                    onClick={() => {
                      setConfirming(null)
                      onDelete(s.id)
                    }}
                    disabled={streaming && current}
                  >
                    confirm — forget this conversation
                  </button>
                ) : (
                  <button
                    className="cursor-pointer transition-colors hover:text-ink"
                    onClick={() => setConfirming(s.id)}
                    title="Delete"
                    disabled={streaming && current}
                  >
                    delete
                  </button>
                )}
              </div>
            )}
            {rowNote(s.id)}
          </div>
        )
      })}
      {sessions.length === 0 && (
        <div className="px-3 py-1.5 text-[11px] text-ink-faint">
          no conversations on this project yet
        </div>
      )}
    </div>
  )
}

export default SessionsFold

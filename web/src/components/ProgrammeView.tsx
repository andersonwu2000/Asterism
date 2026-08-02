import { useState } from 'react'
import { relTime } from '../lib/format'
import { renderProse } from '../lib/prose'
import DiffView from './DiffView'
import type { Programme } from '../lib/types'

/*
 * The Programme, read. ONE renderer for both mount points: the problem
 * page (the archive — every group's chain, at rest) and the Engine's
 * run-scoped tab (the same document while the machine is arguing it).
 * The owner reads this during a run more than any other surface: it is
 * the argument in prose, which beats opening stars one Lean statement
 * at a time (owner, 2026-08-02). Duplicating the RENDERER is what the
 * subtraction rule forbids — reusing it under two framings is not.
 *
 * `extra` is the run flavour's slot (the live proposal↔reviewer cycle):
 * the archive has nothing to put there.
 */

export function GroupPicker({
  data,
  group,
  liveIds,
  onPick,
}: {
  data: Programme
  group: number | null
  /** groups with a strategist seated right now — the run-scoped mount
   * knows this; the archive does not, and shows no dots */
  liveIds?: number[]
  onPick: (id: number | null) => void
}) {
  const groups = data.groups ?? []
  // only a problem that HAS delegated shows this — one group is the
  // ordinary case and must read exactly as it did before groups
  if (groups.filter((g) => !g.is_top).length === 0) return null
  return (
    <div className="mb-4 flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-[11px] text-ink-faint">arguing:</span>
      {groups.map((g) => {
        const on = g.is_top ? group === null : group === g.id
        const livingHere = liveIds?.includes(g.id) ?? false
        const settled = g.status !== 'active'
        return (
          <button
            key={g.id}
            className={`flex max-w-64 items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] transition-colors ${
              on
                ? 'border-edge-strong text-ink'
                : 'border-edge text-ink-faint hover:text-ink-dim'
            }`}
            onClick={() => onPick(g.is_top ? null : g.id)}
            title={
              (g.is_top
                ? "the problem's own argument"
                : `a claim handed to its own group — ${g.status}\n\n${g.charter}`) +
              (livingHere ? '\n\nits strategist is seated right now' : '')
            }
          >
            {livingHere && (
              <span className="size-1 shrink-0 rounded-full bg-starlight" aria-hidden />
            )}
            <span className={`truncate ${settled ? 'line-through decoration-ink-faint/60' : ''}`}>
              {g.is_top ? 'the problem' : g.charter || `group ${g.id}`}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** What the last accepted revision changed in the argument. Folded by
 * default: the body below is the thing to read, this answers "what
 * moved since I last looked" — the question a watcher actually has. */
function WhatChanged({ data }: { data: Programme }) {
  const [open, setOpen] = useState(false)
  const prev = data.previous
  const cur = data.current
  if (!prev || !cur) return null
  return (
    <div className="mb-4">
      <button
        className="flex items-center gap-1.5 text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
        onClick={() => setOpen((v) => !v)}
      >
        <span
          className={`inline-block text-[9px] transition-transform duration-150 ${open ? 'rotate-90' : ''}`}
          aria-hidden
        >
          ▸
        </span>
        what rev {cur.rev} changed — against rev {prev.rev}
      </button>
      {open && (
        <div className="mt-2">
          <DiffView
            left={prev.body}
            right={cur.body}
            label={`rev ${prev.rev} → rev ${cur.rev}`}
          />
        </div>
      )}
    </div>
  )
}

export default function ProgrammeView({
  data,
  group,
  liveIds,
  onPickGroup,
  extra,
}: {
  data: Programme
  group: number | null
  liveIds?: number[]
  onPickGroup: (id: number | null) => void
  extra?: React.ReactNode
}) {
  const picker = (
    <GroupPicker data={data} group={group} liveIds={liveIds} onPick={onPickGroup} />
  )
  if (data.current === null)
    return (
      <div className="mx-auto max-w-3xl px-6 py-5">
        {picker}
        {extra}
        <div className="py-6 text-sm text-ink-faint">
          no programme yet — the first passed proposal will start the revision chain
        </div>
      </div>
    )
  const cur = data.current
  const rejected = data.history.filter((h) => h.status === 'rejected').length
  return (
    <div className="mx-auto max-w-3xl px-6 py-5">
      {picker}
      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px] text-ink-faint">
        <span
          className="text-ink-dim"
          title="the revision chain: each passed proposal advances the Programme by one rev"
        >
          rev {cur.rev}
        </span>
        <span title="how many criticism rounds this revision survived before the adversarial reviewer let it pass">
          {cur.rounds === 0
            ? 'passed adversarial review unchallenged'
            : `passed after ${cur.rounds} round${cur.rounds === 1 ? '' : 's'} of adversarial review`}
        </span>
        <span>{relTime(cur.created_at)}</span>
        {rejected > 0 && (
          <span title="proposals the adversarial reviewer discarded outright — their drafts and the full criticism stay in the engine's records">
            {rejected} rejected along the way
          </span>
        )}
      </div>
      {extra}
      <WhatChanged data={data} />
      {cur.reservations.length > 0 && (
        <div className="mb-4 rounded-xl border border-edge bg-surface px-3.5 py-2.5">
          <div className="mb-1 text-[11px] tracking-wider text-ink-faint uppercase">
            reviewer's reservations — caveats it passed WITH, on the record
          </div>
          <ul className="space-y-1 pl-4 text-[12px] text-ink-dim">
            {cur.reservations.map((r, i) => (
              <li key={i} className="list-disc marker:text-ink-faint">
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="text-sm leading-relaxed text-ink-dim">
        {renderProse(cur.body, { mode: 'document' })}
      </div>
    </div>
  )
}

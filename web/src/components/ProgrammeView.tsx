import { useState } from 'react'
import { relTime } from '../lib/format'
import { emitGoalOpen } from '../lib/goalFocus'
import { charterTitle, groupMeta, treeRows } from '../lib/groupTree'
import { renderProse } from '../lib/prose'
import { navigate } from '../lib/router'
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

/** The discussion tree: who handed what to whom, out of which
 * revision, and what each has built. Indentation IS the delegation —
 * a flat chip row read as three peer things when they are one
 * argument that handed pieces of itself out (owner, 2026-08-07). */
export function GroupTree({
  data,
  group,
  liveIds,
  livePhase,
  onPick,
}: {
  data: Programme
  group: number | null
  /** groups with a strategist seated right now — the run-scoped mount
   * knows this; the archive does not, and shows no dots */
  liveIds?: number[]
  /** …and what each seated one is doing this minute */
  livePhase?: Record<number, string>
  onPick: (id: number | null) => void
}) {
  const rows = treeRows(data.groups)
  // only a problem that HAS delegated shows this — one group is the
  // ordinary case and must read exactly as it did before groups
  if (rows.filter((r) => !r.group.is_top).length === 0) return null
  return (
    <div className="mb-5">
      <div className="mb-1 text-[11px] tracking-wider text-ink-faint uppercase">
        arguing
      </div>
      {rows.map(({ group: g, depth }) => {
        const on = g.is_top ? group === null : group === g.id
        const seated = liveIds?.includes(g.id) ?? false
        return (
          <button
            key={g.id}
            className={`flex w-full items-baseline gap-2 rounded-md px-1.5 py-1 text-left text-[11px] transition-colors ${
              on ? 'bg-surface text-ink' : 'text-ink-faint hover:text-ink-dim'
            }`}
            onClick={() => onPick(g.is_top ? null : g.id)}
            title={
              (g.is_top
                ? "the problem's own argument — what it did not hand out"
                : `handed out as its own group\n\n${g.charter}`) +
              (seated ? '\n\nits strategist is seated right now' : '')
            }
          >
            <span
              className="flex min-w-0 items-baseline gap-1.5"
              style={{ paddingLeft: `${depth * 14}px` }}
            >
              {depth > 0 && (
                <span className="shrink-0 text-ink-faint/50" aria-hidden>
                  └
                </span>
              )}
              {seated && (
                <span
                  className="size-1 shrink-0 translate-y-[-1px] rounded-full bg-starlight"
                  aria-hidden
                />
              )}
              <span className={`truncate ${on ? '' : 'text-ink-dim'}`}>
                {charterTitle(g)}
              </span>
            </span>
            <span className="tnum ml-auto shrink-0 text-ink-faint">
              {groupMeta(g, livePhase?.[g.id])}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** What the delegated burdens handed back: the proved bricks a
 * finished group produced, which are now this argument's to cite.
 * Each opens its star where the reader already is. */
function ReturnedBricks({
  data,
  group,
  brickHome,
}: {
  data: Programme
  group: number | null
  /** where to go when no sky on screen can claim the open — the
   * Engine's own console still has one, so a brick opened from the
   * run-scoped mount must not leave the Engine (owner's link law) */
  brickHome?: string
}) {
  // a sub-group's own page is about ITS argument; the inventory of
  // what came home belongs to whoever delegated — the top group
  if (group !== null) return null
  const delivered = (data.groups ?? []).filter(
    (g) => !g.is_top && (g.delivered_bricks?.length ?? 0) > 0,
  )
  if (delivered.length === 0) return null
  return (
    <div className="mt-6 border-t border-edge pt-4">
      <div className="mb-2 text-[11px] tracking-wider text-ink-faint uppercase">
        came back from delegation — yours to cite
      </div>
      {delivered.map((g) => (
        <div key={g.id} className="mb-3">
          <div className="mb-1 flex items-baseline gap-1 text-[11px] text-ink-faint">
            <span className="min-w-0 truncate" title={g.charter}>
              {charterTitle(g)}
            </span>
            {(g.bricks_proved ?? 0) > (g.delivered_bricks?.length ?? 0) && (
              <span className="shrink-0">
                · showing {g.delivered_bricks?.length} of {g.bricks_proved}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {g.delivered_bricks?.map((b) => (
              <button
                key={b.id}
                className="rounded-md border border-edge px-1.5 py-0.5 font-mono text-[11px] text-ink-dim transition-colors hover:text-ink"
                title={`${b.slug} — open this node`}
                onClick={() => {
                  // claimed in place (a mounted sky) → stay; otherwise
                  // go where a sky IS and let it consume the pending
                  // open on arrival
                  if (!emitGoalOpen({ problem: g.problem, slug: b.slug }))
                    navigate(brickHome ?? `/problems/${encodeURIComponent(g.problem)}`)
                }}
              >
                {b.slug}
              </button>
            ))}
          </div>
        </div>
      ))}
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
  livePhase,
  onPickGroup,
  extra,
  brickHome,
}: {
  data: Programme
  group: number | null
  liveIds?: number[]
  livePhase?: Record<number, string>
  onPickGroup: (id: number | null) => void
  extra?: React.ReactNode
  brickHome?: string
}) {
  const picker = (
    <GroupTree
      data={data}
      group={group}
      liveIds={liveIds}
      livePhase={livePhase}
      onPick={onPickGroup}
    />
  )
  if (data.current === null)
    return (
      <div className="mx-auto max-w-3xl px-6 py-5">
        {picker}
        {extra}
        <div className="py-6 text-sm text-ink-faint">
          no programme yet — the first passed proposal will start the revision chain
        </div>
        <ReturnedBricks data={data} group={group} brickHome={brickHome} />
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
      <ReturnedBricks data={data} group={group} brickHome={brickHome} />
    </div>
  )
}

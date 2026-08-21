import { useState } from 'react'
import { emitGoalOpen } from '../lib/goalFocus'
import {
  charterTitle,
  groupMeta,
  groupTone,
  isStub,
  prunedTreeRows,
  stubBreakdown,
} from '../lib/groupTree'
import type { GroupTone } from '../lib/groupTree'
import { renderProse } from '../lib/prose'
import { navigate } from '../lib/router'
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
/** The row's state as a glyph, in the sky's own terms: a filled disc
 * carries light while it is alive, a settled one recedes, and a
 * hollow ring is a branch that came back with nothing. Same idiom as
 * a star — no new device, and no line through anything. */
function GroupGlyph({ tone }: { tone: GroupTone }) {
  const hollow = tone === 'settled'
  const color =
    tone === 'live' || tone === 'idle'
      ? 'var(--color-starlight)'
      : 'var(--color-ink-faint)'
  return (
    <svg
      width="7"
      height="7"
      viewBox="0 0 8 8"
      className="mt-[5px] shrink-0"
      style={{ opacity: tone === 'live' ? 1 : tone === 'idle' ? 0.7 : 0.5 }}
      aria-hidden
    >
      <circle
        cx="4"
        cy="4"
        r={hollow ? 2.6 : 3}
        fill={hollow ? 'none' : color}
        stroke={hollow ? color : 'none'}
        strokeWidth="1.2"
      />
    </svg>
  )
}

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
  // the settled mass folds into per-parent stubs (113 groups, 101 of
  // them corpses — union_closed 2026-08-22); the reader unfolds one
  // level per click, and the fold resets with the mount
  const [unfolded, setUnfolded] = useState<Set<number | null>>(new Set())
  const rows = prunedTreeRows(data.groups, group, unfolded)
  // only a problem that HAS delegated shows this — one group is the
  // ordinary case and must read exactly as it did before groups
  if ((data.groups ?? []).filter((g) => !g.is_top).length === 0) return null
  return (
    <div className="mb-5">
      <div className="mb-1 flex items-baseline gap-3">
        <span className="text-[11px] tracking-wider text-ink-faint uppercase">arguing</span>
        {unfolded.size > 0 && (
          <button
            className="text-[10.5px] text-ink-faint transition-colors hover:text-ink-dim"
            onClick={() => setUnfolded(new Set())}
            title="fold the settled groups away again"
          >
            fold settled
          </button>
        )}
      </div>
      {rows.map((row) => {
        if (isStub(row)) {
          return (
            <button
              key={`stub-${row.parent ?? 'root'}`}
              className="block w-full rounded-md px-1.5 py-0.5 text-left transition-colors hover:bg-surface/60"
              onClick={() => setUnfolded((old) => new Set(old).add(row.parent))}
              title={`${stubBreakdown(row)} — show them`}
            >
              <span
                className="flex items-baseline gap-1.5 text-[11px] text-ink-faint"
                style={{ paddingLeft: `${row.depth * 14}px` }}
              >
                {row.depth > 0 && (
                  <span className="shrink-0 text-ink-faint/50" aria-hidden>
                    └
                  </span>
                )}
                <span aria-hidden>▸</span>
                <span className="tnum">
                  {row.hidden} settled
                </span>
              </span>
            </button>
          )
        }
        const { group: g, depth } = row
        const on = g.is_top ? group === null : group === g.id
        const tone = groupTone(g, liveIds?.includes(g.id) ?? false)
        return (
          <button
            key={g.id}
            className={`block w-full rounded-md px-1.5 py-1 text-left transition-colors ${
              on ? 'bg-surface' : 'hover:bg-surface/60'
            }`}
            onClick={() => onPick(g.is_top ? null : g.id)}
            title={
              g.is_top
                ? "the problem's own argument — what it did not hand out"
                : 'a claim handed out as its own group'
            }
          >
            <span
              className="block min-w-0"
              style={{ paddingLeft: `${depth * 14}px` }}
            >
              {/* title line: what the argument calls itself */}
              <span className="flex min-w-0 items-start gap-1.5">
                {depth > 0 && (
                  <span className="shrink-0 text-[11px] leading-5 text-ink-faint/50" aria-hidden>
                    └
                  </span>
                )}
                <GroupGlyph tone={tone} />
                <span
                  className={`truncate text-[12px] ${
                    tone === 'live' || on
                      ? 'text-ink'
                      : tone === 'idle'
                        ? 'text-ink-dim'
                        : 'text-ink-faint'
                  }`}
                >
                  {charterTitle(g)}
                </span>
              </span>
              {/* and under it, where it came from and how it stands —
                  a subtitle, not a column fighting the title for width
                  (owner, 2026-08-07) */}
              <span
                className={`tnum block truncate text-[10.5px] text-ink-faint ${
                  depth > 0 ? 'pl-[13px]' : ''
                }`}
              >
                {groupMeta(g, livePhase?.[g.id])}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** Everything standing AROUND the argument, in ONE card: the claim
 * this group was handed, and the caveats its reviewer passed it with.
 * They are context on the same footing, and three separate boxes
 * above the body read as clutter (owner, 2026-08-07). Each half shows
 * only when it exists — the problem's own argument was handed
 * nothing, and an unchallenged revision carries no reservations. */
function Around({
  charter,
  reservations,
}: {
  charter?: string | null
  reservations: string[]
}) {
  const [full, setFull] = useState(false)
  if (!charter && reservations.length === 0) return null
  // the charter's first paragraph IS the claim; the rest is the
  // parent's reasoning about it, one click away
  const lead = (charter ?? '').split(/\n{2,}/).find((p) => p.trim() !== '') ?? ''
  const hasMore = (charter ?? '').trim().length > lead.trim().length
  return (
    <div className="mb-5 rounded-xl border border-edge bg-surface px-3.5 py-2.5">
      {charter && (
        <>
          <div className="mb-1 text-[11px] tracking-wider text-ink-faint uppercase">
            the claim it was handed
          </div>
          {/* chat mode, not document: a charter opens with its own
              `# Charter: …` heading, and a display-face title inside
              a context card competes with the argument's real title
              right below it */}
          <div className="text-[12.5px] leading-relaxed text-ink-dim">
            {renderProse(full ? charter : lead, { mode: 'chat' })}
          </div>
          {hasMore && (
            <button
              className="mt-1 text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
              onClick={() => setFull((v) => !v)}
            >
              {full ? 'less' : 'the whole charter'}
            </button>
          )}
        </>
      )}
      {charter && reservations.length > 0 && (
        <div className="my-2.5 border-t border-edge" />
      )}
      {reservations.length > 0 && (
        <>
          <div className="mb-1 text-[11px] tracking-wider text-ink-faint uppercase">
            reviewer's reservations — caveats it passed with
          </div>
          <ul className="space-y-1 pl-4 text-[12px] text-ink-dim">
            {reservations.map((r, i) => (
              <li key={i} className="list-disc marker:text-ink-faint">
                {r}
              </li>
            ))}
          </ul>
        </>
      )}
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

export default function ProgrammeView({
  data,
  group,
  liveIds,
  livePhase,
  onPickGroup,
  extra,
  brickHome,
  stale,
}: {
  data: Programme
  group: number | null
  liveIds?: number[]
  livePhase?: Record<number, string>
  onPickGroup: (id: number | null) => void
  extra?: React.ReactNode
  brickHome?: string
  /** the shown argument is the PREVIOUS selection, still on screen
   * while the chosen one loads — the tree stays put and only the
   * reading fades, instead of the whole panel blinking out */
  stale?: boolean
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
  const reading = stale ? 'opacity-40 transition-opacity duration-150' : ''
  if (data.current === null)
    return (
      <div className="mx-auto max-w-3xl px-6 py-5">
        {picker}
        <div className={reading}>
          {extra}
          <Around charter={data.charter} reservations={[]} />
          <div className="py-6 text-sm text-ink-faint">
            no programme yet — the first passed proposal will start the revision chain
          </div>
          <ReturnedBricks data={data} group={group} brickHome={brickHome} />
        </div>
      </div>
    )
  const cur = data.current
  return (
    <div className="mx-auto max-w-3xl px-6 py-5">
      {picker}
      <div className={reading}>
      {/* the revision's own vital signs (rev, rounds survived, age,
          discarded drafts) came off the page: the tree already names
          the rev, and a reader of the STANDING argument does not read
          its provenance (owner, 2026-08-07) */}
      {extra}
      <Around charter={data.charter} reservations={cur.reservations} />
      <div className="text-sm leading-relaxed text-ink-dim">
        {renderProse(cur.body, { mode: 'document' })}
      </div>
      <ReturnedBricks data={data} group={group} brickHome={brickHome} />
      </div>
    </div>
  )
}

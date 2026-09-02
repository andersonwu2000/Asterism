import { useRef, useState } from 'react'
import { usePoll } from '../lib/api'
import { cycleForGroup, resolveGroup, seatedGroups } from '../lib/programmeFocus'
import { projectPath } from '../lib/projectRoute'
import { charterTitle } from '../lib/groupTree'
import { usePublishFocus } from '../lib/focus'
import { groupLabel } from '../lib/format'
import { CycleLine } from './EngineRoom'
import ProgrammeView from '../components/ProgrammeView'
import { GroupCommandSheet } from '../components/CommandSheet'
import { ErrorState } from '../components/ui'
import type { Programme, RunStatus } from '../lib/types'

/*
 * Groups — the discussion tree and what each group currently argues
 * (human_interface_design.md §1.4-2, third bullet: it replaces the
 * Programme page).
 *
 * The two readings the old app had — the archive on the problem page
 * and the live one on the Engine — were the same renderer twice, and
 * the only difference was whether a strategist happened to be seated.
 * They are one section now: the tree is always the tree, and a seat
 * lights the branch it is sitting on.
 */

export default function Groups({
  project,
  problem,
  benched,
}: {
  project: string
  problem: string
  /** the shelf row's own flag — the top group's sheet offers the bench
   * (stop this task) and has to know which direction to offer. The
   * shell already polls the board, so this rides down rather than
   * opening a second poll of the same rows. */
  benched?: boolean
}) {
  // three states, not two: undefined = follow whoever is seated,
  // null = the reader chose the task's own argument, a number = that
  // group
  const [pick, setPick] = useState<number | null | undefined>(undefined)
  // the command sheet for the group on screen (§1.3-2)
  const [acting, setActing] = useState(false)
  // this Project's lanes only — the seat lists used to span the whole
  // fleet and the client filter below was the only thing standing
  // between another shelf's group-less worker and this tree
  const { data: run } = usePoll<RunStatus>(
    `/api/run?project=${encodeURIComponent(project)}`,
    5000,
  )
  // a group id belongs to ONE task — carrying a stale one across would
  // 404 the whole read
  const shownRef = useRef(problem)
  if (shownRef.current !== problem) {
    shownRef.current = problem
    if (pick !== undefined) setPick(undefined)
    if (acting) setActing(false)
  }
  // sibling groups run CONCURRENTLY (that is what the tree buys), so
  // "the seated strategist" can be several — the selection and cycle
  // laws live in lib/programmeFocus, tested there. The seat lists span
  // the whole fleet; only this task's groups may light up.
  const workers = (run?.workers ?? []).filter((w) => !w.group || w.group.problem === problem)
  const seats = seatedGroups(workers)
  const liveIds = seats.map((s) => s.group.id)
  const livePhase: Record<number, string> = {}
  for (const s of seats) {
    const c = s.worker.cycle
    livePhase[s.group.id] = c
      ? c.phase === 'proposing'
        ? 'proposing'
        : `round ${c.round} ${c.phase}`
      : 'thinking'
  }
  const group = resolveGroup(pick, workers)
  const { data, error, stale } = usePoll<Programme>(
    `/api/problems/${encodeURIComponent(problem)}/programme` +
      (group !== null ? `?group=${group}` : ''),
    15000,
    // switching branch swaps ONE panel on an otherwise unchanged page:
    // unmounting it read as a flash (owner, 2026-08-07)
    { keepPrevious: true },
  )
  // the cycle shown must belong to the argument ON SCREEN — matched by
  // the group id the server reports, never a sibling's round
  const cycle = cycleForGroup(workers, data?.group_id)
  // the Assistant is told which group's Programme is on screen — the
  // server's own answer, so it can never name a sibling's argument
  usePublishFocus({ problem, group_id: data?.group_id ?? null })
  if (error) return <ErrorState error={error} />
  if (!data) return null
  // which group the reader is standing on — the server's own answer,
  // never the picker's, so the sheet and the argument on screen are
  // about the same charter
  const shown =
    (data.groups ?? []).find((g) => g.id === data.group_id) ??
    (data.groups ?? []).find((g) => g.is_top) ??
    null
  return (
    <div className="px-2 py-4">
      <ProgrammeView
        data={data}
        group={group}
        liveIds={liveIds}
        livePhase={livePhase}
        onPickGroup={setPick}
        stale={stale}
        // a delivered brick opens on the SKY next door — the section is
        // one click away, so leaving the Project to read a node this
        // shell can show is the defect the link audit removed
        brickHome={projectPath(project, 'sky', problem)}
        extra={
          <>
            {cycle && (
              <div className="mb-4 rounded-xl border border-edge bg-surface px-3.5 py-2.5">
                <div className="text-[11px] tracking-wider text-ink-faint uppercase">
                  being revised right now
                </div>
                <CycleLine cycle={cycle} />
              </div>
            )}
            {shown &&
              (acting ? (
                <GroupCommandSheet
                  problem={problem}
                  groupId={shown.id}
                  isTop={shown.is_top}
                  benched={benched}
                  label={groupLabel(shown.id, charterTitle(shown))}
                  onClose={() => setActing(false)}
                />
              ) : (
                <button
                  className="mb-4 cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
                  onClick={() => setActing(true)}
                  title={
                    shown.is_top
                      ? "the task's own argument — what a person may do to it"
                      : 'hand this charter back to the group above it'
                  }
                >
                  act on this group…
                </button>
              ))}
          </>
        }
      />
    </div>
  )
}

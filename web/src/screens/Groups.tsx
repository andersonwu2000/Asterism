import { useRef, useState } from 'react'
import { usePoll } from '../lib/api'
import { cycleForGroup, resolveGroup, seatedGroups } from '../lib/programmeFocus'
import { projectPath } from '../lib/projectRoute'
import { CycleLine } from './EngineRoom'
import ProgrammeView from '../components/ProgrammeView'
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
}: {
  project: string
  problem: string
}) {
  // three states, not two: undefined = follow whoever is seated,
  // null = the reader chose the task's own argument, a number = that
  // group
  const [pick, setPick] = useState<number | null | undefined>(undefined)
  const { data: run } = usePoll<RunStatus>('/api/run', 5000)
  // a group id belongs to ONE task — carrying a stale one across would
  // 404 the whole read
  const shownRef = useRef(problem)
  if (shownRef.current !== problem) {
    shownRef.current = problem
    if (pick !== undefined) setPick(undefined)
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
  if (error) return <ErrorState error={error} />
  if (!data) return null
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
          cycle ? (
            <div className="mb-4 rounded-xl border border-edge bg-surface px-3.5 py-2.5">
              <div className="text-[11px] tracking-wider text-ink-faint uppercase">
                being revised right now
              </div>
              <CycleLine cycle={cycle} />
            </div>
          ) : null
        }
      />
    </div>
  )
}

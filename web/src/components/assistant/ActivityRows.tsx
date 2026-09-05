import { useEffect, useState } from 'react'
import { summarizeTools, toolLine } from '../../lib/chatStream'
import type { ToolRow } from '../../lib/chatStream'

/*
 * What the turn DID, while it does it (assistant_redesign_2026-09-06
 * §1). One row per tool call: a state dot, the tool's name in mono, one
 * line of argument in faint ink, the duration right-aligned. Brightness
 * and shape carry the state — a hollow dot pulses while the call runs,
 * a filled one says it returned, `!` says it did not.
 *
 * A turn with no tool calls draws no timeline at all: the settled norm
 * earns no ink (DESIGN.md). On `done` the rows fold into one line the
 * reader can open again.
 */

const STAGE_LABEL: Record<string, string> = {
  context: 'gathering context…',
  thinking: 'thinking…',
  reading: 'reading the workspace…',
  retry: 'reconnecting…',
}

/** The stage line, in the engine's own vocabulary turned into words. */
export function StageLine({ stage }: { stage: string | null }) {
  if (stage === null) return null
  return <div className="text-[11px] text-ink-faint">{STAGE_LABEL[stage] ?? 'thinking…'}</div>
}

function secs(ms: number): string {
  const s = ms / 1000
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

function Dot({ row }: { row: ToolRow }) {
  if (row.running)
    return (
      <span
        className="h-1.5 w-1.5 animate-pulse rounded-full border border-ink-dim"
        aria-hidden
      />
    )
  if (row.ok === false)
    return (
      <span className="text-[11px] leading-none font-medium text-ink" aria-hidden>
        !
      </span>
    )
  return <span className="h-1.5 w-1.5 rounded-full bg-ink-faint" aria-hidden />
}

function Row({ row, now }: { row: ToolRow; now: number }) {
  const arg = toolLine(row.name, row.input)
  const ms = row.running ? Math.max(0, now - row.startedAt) : row.ms
  return (
    <div className="flex items-baseline gap-2 py-[3px] text-[11px]">
      <span className="flex w-2 shrink-0 justify-center self-center">
        <Dot row={row} />
      </span>
      <span className="shrink-0 font-mono text-ink-dim">{row.name}</span>
      <span className="min-w-0 flex-1 truncate text-ink-faint" title={arg}>
        {arg}
      </span>
      <span className="tnum shrink-0 text-ink-faint">
        {row.running ? 'running' : ms === null ? '' : secs(ms)}
      </span>
    </div>
  )
}

export function ActivityRows({
  rows,
  stage,
  collapsed,
  onToggle,
}: {
  rows: ToolRow[]
  stage: string | null
  /** folded into its summary line — a finished turn opens folded */
  collapsed: boolean
  onToggle: () => void
}) {
  // a running row's duration is the browser's own clock, so it has to
  // be redrawn while nothing else changes
  const live = rows.some((r) => r.running)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!live) return
    const t = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(t)
  }, [live])

  if (rows.length === 0) return <StageLine stage={stage} />
  if (collapsed)
    return (
      <button
        className="mt-2 flex w-full cursor-pointer items-center gap-2 text-[10px] text-ink-faint transition-colors hover:text-ink-dim"
        onClick={onToggle}
        title="what it did to answer"
      >
        <span className="h-px flex-1 bg-edge" />
        <span className="tnum">{summarizeTools(rows)} ▸</span>
        <span className="h-px flex-1 bg-edge" />
      </button>
    )
  return (
    <div>
      {rows.map((r, i) => (
        <Row key={`${r.id}-${i}`} row={r} now={now} />
      ))}
      <StageLine stage={stage} />
      {!live && (
        <button
          className="mt-1 cursor-pointer text-[10px] text-ink-faint transition-colors hover:text-ink-dim"
          onClick={onToggle}
        >
          ▾ fold
        </button>
      )}
    </div>
  )
}

export default ActivityRows

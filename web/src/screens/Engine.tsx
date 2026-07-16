import { useState } from 'react'
import { usePoll } from '../lib/api'
import { Link } from '../lib/router'
import RunConsole from './Run'
import { SettingsTab, UsageTab } from './Telemetry'
import ManifestEditor from '../components/ManifestEditor'
import { TabNav } from '../components/ui'
import type { DaemonStatus, RunStatus } from '../lib/types'

/*
 * Engine — the machine's one door (owner, 2026-07-14: Run + Settings
 * described the same machine from two pages, and the cost surfaces
 * had started duplicating). Four faces of one thing:
 *   Console  — what is it doing right now (instruments, not knobs)
 *   Manifest — steer the live run (hot-reloaded instructions)
 *   Settings — knobs + account (read once at run start)
 *   Usage    — the ledger (per-problem, per-agent-kind)
 * Page anatomy matches Problem/Library chapter exactly: title, TabNav,
 * content — one container, no extra rules.
 */

export type EngineTab = 'console' | 'manifest' | 'settings' | 'usage'

const TABS: { id: EngineTab; label: string; href: string; title?: string }[] = [
  { id: 'console', label: 'Console', href: '/engine' },
  {
    id: 'manifest',
    label: 'Manifest',
    href: '/engine/manifest',
    title: 'steer the live run — saved instructions reach the next agent, no restart',
  },
  { id: 'settings', label: 'Settings', href: '/engine/settings' },
  { id: 'usage', label: 'Usage', href: '/engine/usage' },
]

/** The steering face: the LIVE run's Manifest, editable in place —
 * instructions are hot-reloaded (each agent reads them at spawn), so
 * this is the one lever that reaches a run in flight. */
function SteerManifest() {
  const { data } = usePoll<DaemonStatus>('/api/daemon', 3000)
  const { data: run } = usePoll<RunStatus>('/api/run', 5000)
  const [, setDirty] = useState(false)
  // the engine's scope while running; the last run's focus when idle
  const problem = data?.scope ?? run?.problem ?? null
  if (!problem)
    return (
      <p className="mt-6 text-xs text-ink-faint">
        No run in focus — open a problem on the{' '}
        <Link to="/" className="underline decoration-edge-strong underline-offset-2 hover:text-ink">
          Board
        </Link>{' '}
        to edit its instructions there.
      </p>
    )
  return (
    <div className="mt-4">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs">
        <Link
          to={`/problems/${encodeURIComponent(problem)}`}
          className="font-mono text-ink underline decoration-edge-strong underline-offset-2 hover:text-starlight"
          title="open the problem — sky, goals, timeline"
        >
          {problem}
        </Link>
        <span className="text-ink-faint">
          {data?.running
            ? 'the run is live — saved instructions reach the next agent it spawns, no restart'
            : 'saved instructions apply when the next run starts'}
        </span>
      </div>
      <ManifestEditor problem={problem} onDirtyChange={setDirty} bridged={false} />
    </div>
  )
}

export default function Engine({ tab }: { tab: EngineTab }) {
  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      <h1 className="font-display text-[22px] font-medium text-ink">Engine</h1>
      <TabNav className="mt-3" tabs={TABS} active={tab} />
      {tab === 'console' && <RunConsole />}
      {tab === 'manifest' && <SteerManifest />}
      {tab === 'settings' && (
        <div className="mt-5">
          <SettingsTab />
        </div>
      )}
      {tab === 'usage' && (
        <div className="mt-5">
          <UsageTab />
        </div>
      )}
    </div>
  )
}

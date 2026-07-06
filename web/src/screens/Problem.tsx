import { useState } from 'react'
import { usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { relTime } from '../lib/format'
import { ErrorState, StatusBadge } from '../components/ui'
import Constellation from '../components/Constellation'
import GoalPanel from '../components/GoalPanel'
import StrategyPanel from '../components/StrategyPanel'
import DecisionTimeline from '../components/DecisionTimeline'
import FileViewer from '../components/FileViewer'
import type { Goal, ProblemDetail } from '../lib/types'

type Tab = 'stars' | 'goals' | 'timeline' | 'files'

const GOAL_STATUS_CLS: Record<string, string> = {
  proved: 'text-star',
  attempting: 'text-accent',
  open: 'text-accent',
  shelved: 'text-ink-faint',
  pending_strategist_review: 'text-warn',
  disproved: 'text-danger',
  dead: 'text-ink-faint',
  frozen: 'text-ink-faint',
}

function GoalsList({
  goals,
  onSelect,
}: {
  goals: Goal[]
  onSelect: (id: number) => void
}) {
  if (goals.length === 0)
    return <div className="px-4 py-8 text-center text-xs text-ink-faint">No goals yet.</div>
  return (
    <table className="w-full border-collapse text-left">
      <thead>
        <tr className="border-b border-edge text-xs text-ink-faint">
          <th className="py-2 pr-4 pl-4 font-medium">goal</th>
          <th className="py-2 pr-4 font-medium">status</th>
          <th className="py-2 pr-4 font-medium">origin</th>
          <th className="py-2 pr-4 font-medium">statement</th>
          <th className="py-2 pr-4 text-right font-medium">attempts</th>
        </tr>
      </thead>
      <tbody>
        {goals.map((g) => (
          <tr
            key={g.id}
            className="cursor-pointer border-b border-edge/60 hover:bg-surface"
            onClick={() => onSelect(g.id)}
          >
            <td className="py-2 pr-4 pl-4 font-mono text-xs whitespace-nowrap text-ink">
              {g.slug}
              {g.is_deliverable && <span className="ml-1.5 text-star" title="deliverable">◈</span>}
            </td>
            <td className={`py-2 pr-4 text-xs ${GOAL_STATUS_CLS[g.status] ?? 'text-ink-dim'}`}>
              {g.status}
            </td>
            <td className="py-2 pr-4 text-xs text-ink-faint">{g.origin}</td>
            <td className="max-w-md truncate py-2 pr-4 font-mono text-[11px] text-ink-dim">
              {g.statement}
            </td>
            <td className="py-2 pr-4 text-right text-xs text-ink-faint">
              {g.attempts > 0 ? g.attempts : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function Problem({ name }: { name: string }) {
  const { data, error, loading } = usePoll<ProblemDetail>(
    `/api/problems/${encodeURIComponent(name)}`,
  )
  const [tab, setTab] = useState<Tab>('stars')
  const [selectedGoal, setSelectedGoal] = useState<number | null>(null)
  const [selectedStrategy, setSelectedStrategy] = useState<number | null>(null)
  const [fileToOpen, setFileToOpen] = useState<string | null>(null)

  if (loading) return <div className="p-8 text-sm text-ink-faint">Loading…</div>
  if (error && !data) return <ErrorState error={error} />
  if (!data) return null

  const proved = data.goals.filter((g) => g.status === 'proved').length

  const tabs: { id: Tab; label: string }[] = [
    { id: 'stars', label: 'Constellation' },
    { id: 'goals', label: `Goals (${data.goals.length})` },
    { id: 'timeline', label: 'Timeline' },
    { id: 'files', label: 'Files' },
  ]

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-edge px-6 pt-4">
        <div className="flex items-baseline justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-base font-semibold">{data.name}</h1>
            <StatusBadge status={data.status} />
          </div>
          <div className="flex items-center gap-3">
            {data.goals.length > 0 && (
              <div className="flex h-[3px] w-28 overflow-hidden rounded-full bg-surface-3">
                <div
                  className="h-full bg-starlight/80 transition-[width] duration-700"
                  style={{ width: `${(proved / data.goals.length) * 100}%` }}
                />
                <div
                  className="h-full bg-accent/50 transition-[width] duration-700"
                  style={{
                    width: `${(data.goals.filter((g) => g.status === 'open' || g.status === 'attempting').length / data.goals.length) * 100}%`,
                  }}
                />
              </div>
            )}
            <div className="tnum text-xs text-ink-faint">
              {proved}/{data.goals.length} proved
              {data.ingested_at && ` · ingested ${relTime(data.ingested_at)}`}
              {data.library_bridged_at && ` · bridged ${relTime(data.library_bridged_at)}`}
            </div>
          </div>
        </div>
        {(data.status === 'awaiting_human' || data.status === 'signoff_pending') && (
          <div className="mt-2 rounded-md border border-danger/40 bg-danger/10 px-3 py-1.5 text-xs text-danger">
            This problem is paused on a human decision —{' '}
            <Link to="/inbox" className="underline">
              open the inbox
            </Link>
            .
          </div>
        )}
        <nav className="mt-3 flex gap-5">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={`relative pb-2 text-xs transition-colors duration-150 ${
                tab === t.id ? 'text-ink' : 'text-ink-dim hover:text-ink'
              }`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {tab === t.id && (
                <span className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-accent" />
              )}
            </button>
          ))}
        </nav>
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto">
          {tab === 'stars' && (
            <div className="h-full">
              <Constellation
                goals={data.goals}
                strategies={data.strategies}
                strategyEdges={data.strategy_edges}
                selectedId={selectedGoal}
                onSelect={(id) => {
                  setSelectedGoal(id)
                  if (id !== null) setSelectedStrategy(null)
                }}
                onSelectStrategy={(id) => {
                  setSelectedStrategy(id)
                  setSelectedGoal(null)
                }}
                shelveThreshold={data.shelve_threshold}
              />
            </div>
          )}
          {tab === 'goals' && <GoalsList goals={data.goals} onSelect={setSelectedGoal} />}
          {tab === 'timeline' && (
            <div className="mx-auto max-w-4xl px-4 py-3">
              <DecisionTimeline decisions={data.decisions} />
            </div>
          )}
          {tab === 'files' && (
            <div className="flex h-full">
              <FileViewer
                problem={data.name}
                proofFiles={data.proof_files}
                initialFile={fileToOpen}
              />
            </div>
          )}
        </div>
        {selectedGoal !== null && tab !== 'files' && tab !== 'timeline' && (
          <GoalPanel
            problem={data.name}
            goalId={selectedGoal}
            onClose={() => setSelectedGoal(null)}
            onSelectStrategy={(id) => {
              setSelectedStrategy(id)
              setSelectedGoal(null)
            }}
            onOpenFile={(rel) => {
              setFileToOpen(rel)
              setTab('files')
            }}
          />
        )}
        {selectedGoal === null &&
          selectedStrategy !== null &&
          tab !== 'files' &&
          tab !== 'timeline' && (
            <StrategyPanel
              problem={data.name}
              strategyId={selectedStrategy}
              onClose={() => setSelectedStrategy(null)}
              onSelectGoal={(id) => {
                setSelectedGoal(id)
                setSelectedStrategy(null)
              }}
            />
          )}
      </div>
    </div>
  )
}

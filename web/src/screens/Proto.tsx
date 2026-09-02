import { useState } from 'react'
import { Link, useRoute } from '../lib/router'
import { frameClass } from '../lib/textFrame'
import { Lean } from '../lib/lean'
import { QuotaMeter } from './Run'
import { SectionLabel } from '../components/ui'

/*
 * THROWAWAY — the information-architecture mock for
 * human_interface_design.md §1.4, so the shape can be judged before it
 * is built (implementation order step 3: "先做資訊架構原型再實作").
 *
 * Everything here is static. It uses the app's real tokens, fonts and
 * radius ladder and nothing else, so what the screenshots show is what
 * the shell would look like. DELETE THIS FILE when §1.4 lands for
 * real — it is a drawing, not a component library.
 *
 *   #/proto                   the Project picker (the entry page)
 *   #/proto/<project>/<sect>  inside a Project: top menu, left column
 */

/* ------------------------------------------------------------------ */
/* the two glyphs the top-right corner is allowed (§1.4-2)             */
/* ------------------------------------------------------------------ */

/** two sliders — the gear, borrowed verbatim from the sidebar's
 * Settings row so the one settings page keeps one mark */
const GEAR = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
    <path d="M2 5.5h12M2 10.5h12" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" opacity="0.55" />
    <circle cx="10" cy="5.5" r="1.7" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
    <circle cx="6" cy="10.5" r="1.7" fill="var(--color-surface)" stroke="currentColor" strokeWidth="1.1" />
  </svg>
)

/** the conversation glyph the console already owns (a bubble with a
 * star in it) — the Assistant inherits Ask's mark, not its word */
const ASSISTANT = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
    <path
      d="M2.5 3.5A1.5 1.5 0 014 2h8a1.5 1.5 0 011.5 1.5v6A1.5 1.5 0 0112 11H7.2L4.5 13.6V11H4a1.5 1.5 0 01-1.5-1.5v-6z"
      stroke="currentColor"
      strokeWidth="1.1"
      strokeLinejoin="round"
    />
    <circle cx="8" cy="6.5" r="1.3" fill="currentColor" opacity="0.85" />
  </svg>
)

const HELP = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
    <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.1" opacity="0.6" />
    <path
      d="M6.3 6.2a1.75 1.75 0 013.4.6c0 1.2-1.7 1.4-1.7 2.6"
      stroke="currentColor"
      strokeWidth="1.1"
      strokeLinecap="round"
    />
    <circle cx="8" cy="11.6" r="0.75" fill="currentColor" />
  </svg>
)

const MARK = (
  <svg width="18" height="18" viewBox="0 0 20 20" className="text-star" aria-hidden>
    <path d="M4 14.5L10.5 5l5 6.5" stroke="currentColor" strokeWidth="0.9" opacity="0.5" fill="none" />
    <circle cx="4" cy="14.5" r="1.7" fill="currentColor" />
    <circle cx="10.5" cy="5" r="2.1" fill="currentColor" />
    <circle cx="15.5" cy="11.5" r="1.4" fill="currentColor" />
  </svg>
)

function IconButton({
  children,
  title,
  live,
}: {
  children: React.ReactNode
  title: string
  live?: boolean
}) {
  return (
    <button
      title={title}
      className="relative cursor-pointer rounded-full p-1.5 text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
    >
      {children}
      {live && (
        <span className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-starlight" />
      )}
    </button>
  )
}

/* ------------------------------------------------------------------ */
/* 1. the Project picker                                               */
/* ------------------------------------------------------------------ */

/** names and counts are this workspace's real `/api/projects`;
 * descriptions are invented (the column is empty everywhere on disk)
 * so both shapes — written and blank — can be judged. */
const PROJECTS: { name: string; description: string; tasks: number; running?: number }[] = [
  { name: 'Algebra', description: '', tasks: 1 },
  { name: 'Analysis', description: '', tasks: 1 },
  {
    name: 'Combinatorics',
    description: 'The union-closed sets conjecture and the lemmas around it.',
    tasks: 1,
  },
  {
    name: 'Erdos',
    description: 'Open entries from the Erdős problem collection, one task each.',
    tasks: 5,
    running: 1,
  },
  {
    name: 'Geometry',
    description: 'de Rham, currents, and the Stokes programme.',
    tasks: 30,
  },
  { name: 'LinearAlgebra', description: '', tasks: 14 },
  { name: 'Logic', description: '', tasks: 5 },
  { name: 'Minif2f', description: 'The miniF2F benchmark, imported whole.', tasks: 244 },
  { name: 'NumberTheory', description: '', tasks: 1 },
  { name: 'Putnam', description: 'Putnam competition problems.', tasks: 49 },
  { name: 'PutnamCmp', description: 'Paired control runs against the Putnam set.', tasks: 2 },
  { name: 'Test', description: 'Probes for the engine itself — not mathematics.', tasks: 11 },
  { name: 'Topology', description: '', tasks: 4 },
  { name: 'pi1_circle', description: '', tasks: 1 },
  { name: 'residue_thm', description: '', tasks: 1 },
  { name: 'sl2_v_n_irreducible', description: '', tasks: 1 },
  { name: 'sylvester_gallai', description: '', tasks: 1 },
  { name: 'yajyuusenbai', description: '', tasks: 1 },
]

function ProjectTile({ p }: { p: (typeof PROJECTS)[number] }) {
  return (
    <Link
      to={`/proto/${p.name}/engine`}
      className="group flex flex-col rounded-xl border border-edge bg-surface p-5 transition-colors duration-150 hover:border-edge-strong hover:bg-surface-2"
    >
      <div className="font-display text-[18px] text-ink">{p.name}</div>
      <p className="mt-1.5 min-h-[3.1em] text-[12.5px] leading-relaxed text-ink-dim">
        {p.description}
      </p>
      <div className="tnum mt-4 flex items-center gap-3 text-[11px] text-ink-faint">
        <span>
          {p.tasks} task{p.tasks === 1 ? '' : 's'}
        </span>
        {p.running ? (
          <span className="flex items-center gap-1.5 text-ink-dim">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            {p.running} running
          </span>
        ) : null}
      </div>
    </Link>
  )
}

function Picker() {
  return (
    <div className="mx-auto max-w-6xl px-8 py-9">
      <header className="mb-9 flex items-center">
        <Link to="/proto" className="flex items-center gap-2">
          {MARK}
          <span className="font-display text-[17px] font-medium">Asterism</span>
        </Link>
        <div className="ml-auto flex items-center gap-1">
          <IconButton title="settings — accounts, machine, appearance">{GEAR}</IconButton>
          <IconButton title="how Asterism works">{HELP}</IconButton>
        </div>
      </header>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {PROJECTS.map((p) => (
          <ProjectTile key={p.name} p={p} />
        ))}
        <button className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-edge p-5 text-[12.5px] text-ink-faint transition-colors hover:border-edge-strong hover:text-ink-dim">
          <span className="mb-1 text-[18px] leading-none">+</span>
          new project
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* 2. inside a Project — the shell                                     */
/* ------------------------------------------------------------------ */

const MENU = [
  { id: 'tasks', label: 'Tasks' },
  { id: 'sky', label: 'Sky' },
  { id: 'groups', label: 'Groups' },
  { id: 'engine', label: 'Engine room' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'documents', label: 'Documents' },
]

/** the Project's tasks. Real Erdos members; the two exception states
 * are staged so the ink for them can be judged (nothing is running in
 * this workspace). */
const TASKS = [
  { name: 'Erdos.p1', state: '' },
  { name: 'Erdos.p143', state: 'needs input' },
  { name: 'Erdos.p358', state: 'running' },
  { name: 'Erdos.p865', state: '' },
  { name: 'Erdos.p912', state: '' },
]

function TaskRail({
  open,
  onToggle,
  selected,
  onSelect,
}: {
  open: boolean
  onToggle: () => void
  selected: string
  onSelect: (n: string) => void
}) {
  if (!open)
    return (
      <div className="shrink-0 border-r border-edge px-2 py-4">
        <button
          onClick={onToggle}
          title="show the task list"
          className="cursor-pointer rounded-md px-1.5 py-1 text-[11px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
        >
          ›
        </button>
      </div>
    )
  return (
    <aside className="w-52 shrink-0 border-r border-edge px-3 py-4">
      <div className="mb-2 flex items-center px-2">
        <span className="tnum text-[11px] text-ink-faint">{TASKS.length} tasks</span>
        <button
          onClick={onToggle}
          title="hide the task list"
          className="ml-auto cursor-pointer rounded-md px-1.5 py-0.5 text-[11px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
        >
          ‹
        </button>
      </div>
      <nav className="flex flex-col gap-0.5">
        {TASKS.map((t) => {
          const active = t.name === selected
          return (
            <button
              key={t.name}
              onClick={() => onSelect(t.name)}
              className={`group relative flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-left font-mono text-[12px] transition-colors duration-150 ${
                active ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:bg-surface-2/60 hover:text-ink'
              }`}
            >
              {active && (
                <span className="absolute top-1.5 bottom-1.5 -left-2 w-0.5 rounded-full bg-star" />
              )}
              <span className="flex-1 truncate">{t.name.replace(/^.*\./, '')}</span>
              {t.state === 'running' && (
                <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-accent" title="the engine is on it" />
              )}
              {t.state === 'needs input' && (
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-warn" title="waiting for your decision" />
              )}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}

/* --- the representative content page: the engine room -------------- */

const SLOTS = [
  {
    kind: 'strategist',
    // a strategist sits on a GROUP: the group code is its unit, so it
    // is named once, in the slug's place — the lane used to carry it
    // twice over
    slug: 'grp7 · delegated',
    group: '',
    age: '4m',
    line: 'round 2 · judging',
    binders: '',
    statement: '',
    charter: 'close the density bound for the sparse case',
    tail: 'plan_note.md',
    quiet: 'writing now',
  },
  {
    kind: 'formalizer',
    slug: 'sum_lower_bound',
    group: 'grp7',
    age: '11m',
    line: '',
    binders: '(hS : S.Nonempty) (hd : ∀ x ∈ S, d x ≤ n)',
    statement: '∑ x ∈ S, f x ≥ (S.card : ℝ) / n',
    tail: 'sum_lower_bound.lean',
    quiet: 'last write 8s ago',
    charter: '',
  },
  {
    kind: 'formalizer',
    slug: 'card_le_of_inj',
    group: 'grp2',
    age: '2m',
    line: '',
    binders: '(h : Function.Injective f)',
    statement: 'A.card ≤ B.card',
    tail: 'card_le_of_inj.lean',
    quiet: 'writing now',
    charter: '',
  },
]

const LOG_LINES = [
  '2026-09-02T11:04:18Z  strategist  grp7  wake routine — 3 open goals, 1 shelved',
  '2026-09-02T11:04:52Z  formalizer  sum_lower_bound  spawned (claude, opus-4.6)',
  '2026-09-02T11:06:07Z  gateway     elaborated Erdos/p358/sum_lower_bound.lean in 41.2s',
  '2026-09-02T11:06:09Z  formalizer  card_le_of_inj  landed — 1 decl, 0 sorry',
  '2026-09-02T11:07:31Z  promotion   cold build s1183 started (2 modules)',
  '2026-09-02T11:08:44Z  strategist  grp7  adversary round 2 — 1 reservation',
  '2026-09-02T11:09:02Z  ledger      worker rss 5.4G / 12.0G budget',
]

function Slot({ s }: { s: (typeof SLOTS)[number] }) {
  return (
    <div className="rounded-xl border border-edge bg-surface p-3">
      <div className="flex items-baseline gap-2.5">
        <span className="text-xs font-medium text-ink">{s.kind}</span>
        <span className="max-w-72 truncate font-mono text-xs text-ink-dim">{s.slug}</span>
        {s.group && (
          <span className="shrink-0 font-mono text-[10.5px] text-ink-faint">{s.group}</span>
        )}
        <span className="tnum ml-auto text-[11px] text-ink-faint">on it {s.age}</span>
      </div>
      {s.statement && (
        <div className="mt-1 font-mono text-[11px] text-ink-faint">
          {s.binders && (
            <div className="truncate opacity-75">
              <Lean code={s.binders} />
            </div>
          )}
          <div className="truncate">
            <Lean code={'⊢ ' + s.statement} />
          </div>
        </div>
      )}
      {s.charter && <div className="mt-1 text-[11px] text-ink-dim">{s.charter}</div>}
      {s.line && <div className="mt-1.5 text-[11px] text-ink-dim">{s.line}</div>}
      <div className="tnum mt-2 flex items-center gap-1.5 text-[10px] text-ink-faint">
        <span aria-hidden>▸</span>
        {s.quiet}
        <span className="font-mono">· {s.tail}</span>
      </div>
    </div>
  )
}

function EngineRoom() {
  return (
    <div className="mx-auto max-w-4xl">
      {/* one status line, no page title — the menu already says where
          you are, and drawing that twice is the law this shell exists
          to stop breaking */}
      <div className="flex items-baseline gap-2.5 text-xs">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
        <span className="text-ink">running</span>
        <span className="font-mono text-ink-dim">Erdos.p358</span>
        <span className="tnum text-ink-faint">47m</span>
      </div>

      <section className="mt-7">
        {/* the pool's capacity is the one fact the list below cannot
            state: three lanes do not say how many there could be */}
        <SectionLabel>slots · 3 of 4 busy</SectionLabel>
        <div className="flex flex-col gap-2">
          {SLOTS.map((s) => (
            <Slot key={s.slug} s={s} />
          ))}
          {/* §1.5-2: a proved goal's cold build is real work with
              nothing on screen to show for it — it looked like the slot
              had simply vanished */}
          <div className="flex items-baseline gap-2.5 rounded-xl border border-edge bg-surface px-3 py-2.5">
            <span className="text-xs text-ink-dim">cold-building</span>
            <span className="font-mono text-xs text-ink-faint">s1183</span>
            <span className="text-[11px] text-ink-faint">2 modules · promotion gate</span>
            <span className="tnum ml-auto text-[11px] text-ink-faint">1m</span>
          </div>
        </div>
      </section>

      <section className="mt-7">
        <SectionLabel>plan usage</SectionLabel>
        <div className="flex flex-wrap items-start gap-x-10 gap-y-5">
          <div className="flex min-w-[17rem] max-w-xl flex-1 basis-0 flex-col gap-2">
            <div className="text-[11px] text-ink-dim">
              Claude Code <span className="text-ink-faint">· strategist · formalizer</span>
            </div>
            <QuotaMeter label="5-hour window" pct={62} resetsAt="2026-09-02T15:00:00Z" />
            <QuotaMeter label="week" pct={88} resetsAt="2026-09-05T09:00:00Z" />
            <QuotaMeter label="fable · week" pct={17} resetsAt="2026-09-05T09:00:00Z" quiet />
          </div>
          <div className="flex min-w-[17rem] max-w-xl flex-1 basis-0 flex-col gap-2">
            <div className="text-[11px] text-ink-dim">
              Codex <span className="text-ink-faint">· adversary</span>
            </div>
            <QuotaMeter label="5-hour window" pct={34} resetsAt="2026-09-02T14:20:00Z" />
            <QuotaMeter label="week" pct={51} resetsAt="2026-09-06T00:00:00Z" />
            <div className="text-[11px] text-ink-faint">as its last agent measured it, 6m ago</div>
          </div>
        </div>
      </section>

      <section className="mt-7">
        <SectionLabel>engine log</SectionLabel>
        {/* one template for every text block (DESIGN.md): the live
            LogTail still hand-rolls `bg-bg` chrome of its own — that is
            a Phase-2 fix, not a second shape */}
        <pre className={frameClass({ cap: 'md', wrap: false })}>{LOG_LINES.join('\n')}</pre>
      </section>
    </div>
  )
}

const SKETCH: Record<string, string> = {
  tasks:
    'the task list with Run/Stop and the run parameters beside it — models per pipeline, time budget, blocked kinds; the Intent editor (the goal, your standing word, anchors and claim) below.',
  sky: 'the constellation, unchanged — plus commands on a star: shelve, inject, mark deliverable.',
  groups: 'the group tree by code and charter; each group its programme history and the debate under each revision.',
  timeline: 'what happened, newest first, every row naming an object you can open.',
  documents: 'the Project document root — the left column becomes the file list.',
}

function ProjectShell({ project, section }: { project: string; section: string }) {
  const [railOpen, setRailOpen] = useState(true)
  const [task, setTask] = useState('Erdos.p358')
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-12 shrink-0 items-center gap-6 border-b border-edge px-5">
        <Link to="/proto" className="flex items-center gap-2" title="all projects">
          {MARK}
          <span className="font-display text-[15px] font-medium text-ink">{project}</span>
        </Link>
        <nav className="flex gap-5">
          {MENU.map((m) => (
            <Link
              key={m.id}
              to={`/proto/${project}/${m.id}`}
              className={`relative py-4 text-xs transition-colors duration-150 ${
                m.id === section ? 'text-ink' : 'text-ink-dim hover:text-ink'
              }`}
            >
              {m.label}
              {m.id === section && (
                <span className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-star" />
              )}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <IconButton title="settings — accounts, machine, appearance">{GEAR}</IconButton>
          <IconButton title="assistant (Ctrl+/)" live>
            {ASSISTANT}
          </IconButton>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <TaskRail
          open={railOpen}
          onToggle={() => setRailOpen((o) => !o)}
          selected={task}
          onSelect={setTask}
        />
        <main className="min-w-0 flex-1 overflow-y-auto px-6 py-6">
          {section === 'engine' ? (
            <EngineRoom />
          ) : (
            <p className="max-w-md text-xs leading-relaxed text-ink-faint">
              {SKETCH[section] ?? ''}
            </p>
          )}
        </main>
      </div>
    </div>
  )
}

export default function Proto() {
  const route = useRoute()
  const project = route.segments[1] ?? ''
  if (!project) return <Picker />
  return <ProjectShell project={project} section={route.segments[2] ?? 'tasks'} />
}

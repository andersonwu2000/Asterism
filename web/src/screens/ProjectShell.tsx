import { useEffect, useMemo } from 'react'
import { usePoll } from '../lib/api'
import { Link, navigate, replace } from '../lib/router'
import {
  SECTIONS,
  SECTION_LABEL,
  TASK_SECTIONS,
  defaultTask,
  projectPath,
  railVisible,
  shelfOrder,
  tasksOf,
} from '../lib/projectRoute'
import type { ProjectRoute, Section } from '../lib/projectRoute'
import { docAddress, docRefFromWorkspacePath } from '../lib/docShell'
import { ASSISTANT, GEAR, IconButton, MARK } from '../components/glyphs'
import Timeline from '../components/Timeline'
import Tasks from './Tasks'
import Sky from './Sky'
import Groups from './Groups'
import EngineRoom from './EngineRoom'
import Docs from './Docs'
import type { BoardProblem, BoardResponse } from '../lib/types'

/*
 * Inside a Project (human_interface_design.md §1.4-2): one header row
 * — where you are, the six places you can go, and the two glyphs — and
 * a collapsible task column beside the content.
 *
 * The header carries the primary menu because a Project's sections are
 * PEERS; the column carries the tasks because they are the same shelf
 * seen from whichever section you are standing in. That is the whole
 * geometry, and it is why no section draws its own title: the menu has
 * already said which one you are reading.
 */

function TaskRow({
  p,
  active,
  to,
}: {
  p: BoardProblem
  active: boolean
  to: string
}) {
  const needsYou = p.status === 'awaiting_human' || p.status === 'signoff_pending'
  return (
    <Link
      to={to}
      title={p.name}
      className={`group relative flex items-center gap-2 rounded-lg px-2.5 py-1.5 font-mono text-[12px] transition-colors duration-150 ${
        active ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:bg-surface-2/60 hover:text-ink'
      }`}
    >
      {active && (
        <span className="absolute top-1.5 bottom-1.5 -left-2 w-0.5 rounded-full bg-star" />
      )}
      <span className="min-w-0 flex-1 truncate">{p.name.replace(/^.*\./, '')}</span>
      {/* exception ink only: the settled majority is a plain name */}
      {p.in_flight > 0 || p.status === 'proving' ? (
        <span
          className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-accent"
          title="the engine is on it"
        />
      ) : needsYou ? (
        <span
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-warn"
          title="waiting for your decision"
        />
      ) : p.status === 'stalled' ? (
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-danger" title="no path forward" />
      ) : null}
    </Link>
  )
}

function TaskRail({
  project,
  section,
  rows,
  current,
  open,
  onToggle,
}: {
  project: string
  section: Section
  rows: BoardProblem[]
  current: string | null
  open: boolean
  onToggle: () => void
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
    <aside className="flex w-52 shrink-0 flex-col border-r border-edge px-3 py-4">
      {/* a count, not the word "Tasks" — the menu above already said it */}
      <div className="mb-2 flex items-center px-2">
        <Link
          to={projectPath(project, 'tasks')}
          className="tnum text-[11px] text-ink-faint transition-colors hover:text-ink-dim"
          title="the whole shelf — run control and run parameters"
        >
          {rows.length} tasks
        </Link>
        <button
          onClick={onToggle}
          title="hide the task list"
          className="ml-auto cursor-pointer rounded-md px-1.5 py-0.5 text-[11px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
        >
          ‹
        </button>
      </div>
      {/* the shelf's ONE order (projectRoute.shelfOrder) — the column,
          the shelf table and the task a section opens on are three
          readings of one list, and a reader switching section must not
          watch it reshuffle */}
      <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
        {shelfOrder(rows).map((p) => (
          <TaskRow
            key={p.name}
            p={p}
            active={p.name === current}
            to={projectPath(project, section, p.name)}
          />
        ))}
      </nav>
    </aside>
  )
}

export default function ProjectShell({
  route,
  railOpen,
  onToggleRail,
  chatOpen,
  chatStreaming,
  chatUnread,
  onToggleChat,
}: {
  route: ProjectRoute
  railOpen: boolean
  onToggleRail: () => void
  chatOpen: boolean
  chatStreaming: boolean
  chatUnread: boolean
  onToggleChat: () => void
}) {
  const { project, section, problem } = route
  const { data } = usePoll<BoardResponse>(
    `/api/problems?project=${encodeURIComponent(project)}`,
    5000,
  )
  const rows = useMemo(() => tasksOf(data?.problems ?? [], project), [data, project])
  // Has the shelf ANSWERED yet? Before the first reply `rows` is empty
  // for the same reason an empty shelf is — so every screen below said
  // "nothing here" for a beat on every open, about a Project holding
  // eleven tasks (2026-09-04). An unanswered question is not an answer
  // of zero, and `data` is null until one arrives (an error before the
  // first reading leaves it null too, which is the honest reading: we
  // still do not know what is on this shelf).
  const loaded = data !== null

  // The address and the view must agree: a task section reached without
  // a task picks one (the attention order every other surface reads in)
  // and REWRITES the address, so a reload, a back button and a mailed
  // link all land on the same page.
  //
  // `replace`, not `navigate`: this is the shell's own correction, not
  // a move the reader made, and pushing it made Back unusable — it went
  // to `…/sky`, this effect immediately pushed `…/sky/<task>` again, and
  // the section became a trap you could not leave with the back button
  // (measured in the browser, 2026-09-04).
  useEffect(() => {
    if (!TASK_SECTIONS.includes(section)) return
    if (section === 'tasks' && problem === null) return // the shelf itself
    if (problem !== null && rows.some((p) => p.name === problem)) return
    if (rows.length === 0) return
    const pick = problem !== null && rows.some((p) => p.name === problem)
      ? problem
      : defaultTask(rows)
    if (pick) replace(projectPath(project, section, pick))
  }, [project, section, problem, rows])

  // the shelf page IS the task list; drawing the column beside it would
  // draw the same list twice. Documents brings its own file column.
  const showRail =
    railVisible(rows) && section !== 'docs' && !(section === 'tasks' && problem === null)
  const current = problem ?? (rows.length === 1 ? rows[0].name : null)

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-12 shrink-0 items-center gap-6 border-b border-edge px-5">
        <Link
          to="/"
          className="flex min-w-0 items-center gap-2"
          title="all projects"
        >
          {MARK}
          <span className="truncate font-display text-[15px] font-medium text-ink">
            {project}
          </span>
        </Link>
        <nav data-menu className="flex gap-5">
          {SECTIONS.map((s) => (
            <Link
              key={s}
              to={projectPath(project, s, TASK_SECTIONS.includes(s) ? current : null)}
              className={`relative py-4 text-xs whitespace-nowrap transition-colors duration-150 ${
                s === section ? 'text-ink' : 'text-ink-dim hover:text-ink'
              }`}
            >
              {SECTION_LABEL[s]}
              {s === section && (
                <span className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-star" />
              )}
            </Link>
          ))}
        </nav>
        {/* EXACTLY two, by the owner's ruling (§1.4-2) — the attribute
            is what the smoke suite counts, so a third one added later
            fails a test instead of quietly landing */}
        <div data-corner className="ml-auto flex items-center gap-1">
          <IconButton to="/settings" title="settings — accounts, machine, appearance">
            {GEAR}
          </IconButton>
          <IconButton
            title={
              chatStreaming && !chatOpen
                ? 'assistant — thinking (Ctrl+/)'
                : chatUnread && !chatOpen
                  ? 'assistant — an answer is waiting (Ctrl+/)'
                  : 'assistant — ask about this project (Ctrl+/)'
            }
            onClick={onToggleChat}
            active={chatOpen}
            pulse={chatStreaming && !chatOpen}
            live={chatUnread && !chatOpen}
          >
            {ASSISTANT}
          </IconButton>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        {showRail && (
          <TaskRail
            project={project}
            section={section}
            rows={rows}
            current={current}
            open={railOpen}
            onToggle={onToggleRail}
          />
        )}
        {/* `key={current}` on the task-scoped screens is deliberate and
            stays: it is what guarantees no task's camera, selection or
            open sheet survives into another task. The flash it used to
            cost is gone by another route — `lib/pollCache` hands the
            fresh mount the reading already in hand when the task was
            visited inside its own poll interval, so a switch back paints
            from data rather than from a spinner. */}
        <main className="min-w-0 flex-1 overflow-y-auto">
          {section === 'tasks' ? (
            <Tasks project={project} rows={rows} problem={problem} loaded={loaded} />
          ) : section === 'sky' ? (
            current ? (
              <Sky
                key={current}
                project={project}
                problem={current}
                initialGoal={route.goal}
              />
            ) : (
              /* three different silences, and only one of them is
                 "there is nothing here": the shelf has not answered
                 (wait), it answered with tasks and the address is
                 being rewritten to one (a blink — say nothing), or it
                 answered empty (say so) */
              <Waiting loaded={loaded} empty={rows.length === 0} project={project} />
            )
          ) : section === 'groups' ? (
            current ? (
              <Groups
                key={current}
                project={project}
                problem={current}
                benched={rows.find((p) => p.name === current)?.benched}
              />
            ) : (
              <Waiting loaded={loaded} empty={rows.length === 0} project={project} />
            )
          ) : section === 'engine' ? (
            <EngineRoom project={project} pin={problem} rows={rows} />
          ) : section === 'timeline' ? (
            /* the shelf's whole history when the address names no task,
               one task's when it does (§1.4: a Project surface whose
               secondary menu is the task list) */
            <div className="mx-auto max-w-4xl px-6 py-6">
              <Timeline
                key={problem ?? '@project'}
                path={
                  problem
                    ? `/api/problems/${encodeURIComponent(problem)}/events`
                    : `/api/projects/${encodeURIComponent(project)}/events`
                }
                problem={problem ?? undefined}
                showProblem={problem === null}
                onSelectGoal={(id, p) => {
                  const target = p ?? problem
                  if (target) navigate(projectPath(project, 'sky', target, id))
                }}
                /* a revision row's expansion offers "read the
                   Programme"; without somewhere for it to land the
                   link simply never drew. On the shelf-wide feed the
                   row's OWN task is the target — the reader is scoped
                   to none. */
                onOpenProgramme={(p) => {
                  const target = p ?? problem
                  if (target) navigate(projectPath(project, 'groups', target))
                }}
                /* a theory row landed a FILE, and its expansion offers
                   it. The path is workspace-relative, the Documents tab
                   is root-relative, and a path this Project's shelf does
                   not hold simply has nowhere to go. */
                onOpenDocument={(p) => {
                  const ref = docRefFromWorkspacePath(project, p)
                  if (ref) navigate(docAddress(project, ref))
                }}
              />
            </div>
          ) : (
            <Docs
              project={project}
              problem={current ?? defaultTask(rows)}
              tasks={rows.map((p) => p.name)}
              path={route.rest}
            />
          )}
        </main>
      </div>
    </div>
  )
}

/** What a task section says when it has no task to draw.
 *
 * Only ONE of the three silences is an empty shelf, and saying so
 * before the poll has answered was a false sentence on every open. The
 * wait wears the console's 150ms-delayed idiom, so a read that answers
 * in a blink draws nothing at all. */
function Waiting({
  loaded,
  empty,
  project,
}: {
  loaded: boolean
  empty: boolean
  project: string
}) {
  if (!loaded) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>
  // the shelf answered with tasks; the address is being rewritten to
  // one of them this same beat
  if (!empty) return null
  return <Empty project={project} />
}

/** An empty shelf is legal (§3.1) — say what to do, do not draw a
 * frame around nothing. */
function Empty({ project }: { project: string }) {
  return (
    <div className="mx-auto max-w-lg px-6 py-24 text-center">
      <div className="font-display text-[19px] text-ink-dim">Nothing on this shelf yet</div>
      <p className="mt-2 text-xs leading-relaxed text-ink-faint">
        A task is one thing you want proved, written in plain language.{' '}
        <Link
          to={projectPath(project, 'tasks')}
          className="underline decoration-edge-strong underline-offset-2 hover:text-ink"
        >
          Add the first one
        </Link>
        .
      </p>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { ApiError, apiDelete, apiPatch, apiPost, usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { projectPath } from '../lib/projectRoute'
import { visibleProjects } from '../lib/projectShelf'
import type { ProjectFilter } from '../lib/projectShelf'
import CollectionSearch from '../components/CollectionSearch'
import ProjectSkyPreview from '../components/ProjectSkyPreview'
import { ConfirmWindow } from '../components/ConfirmWindow'
import { GEAR, HelpButton, IconButton, MARK } from '../components/glyphs'
import { Button, ErrorState } from '../components/ui'
import type { ProjectCard } from '../lib/types'

/*
 * The first screen the console opens (human_interface_design.md
 * §1.4-1): the shelves, as tiles. No menu — a Project is chosen here,
 * and everything else happens inside one. The only other affordances
 * are the gear and the help glyph, the same two the Project header
 * carries and the only two either screen has.
 *
 * A tile names the project, its task inventory and any live or human
 * attention. Search and activity filters narrow the collection without
 * changing its alphabetical order. An empty description earns no copy.
 */

/** A shelf's own two acts. They appear on hover and on keyboard focus,
 * because a tile is read far more often than it is renamed — ink is for
 * exceptions (DESIGN.md), and a permanent pair of buttons on every tile
 * would make the grid about its own maintenance. */
function TileActions({
  p,
  onRename,
  onDelete,
}: {
  p: ProjectCard
  onRename: () => void
  onDelete: () => void
}) {
  return (
    <div className="pointer-events-none absolute right-5 top-4 flex justify-end gap-3 opacity-0 transition-opacity duration-150 group-hover:opacity-100 focus-within:opacity-100">
      {(
        [
          ['rename…', onRename, `rename ${p.name} — the tasks keep their names and their folders`],
          ['delete…', onDelete, `remove the ${p.name} shelf`],
        ] as const
      ).map(([label, act, hint]) => (
        <button
          key={label}
          className="pointer-events-auto cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
          title={hint}
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            act()
          }}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

/** Renaming is a table update: `problems.project` follows in the same
 * transaction and NEITHER the task names nor their directories move
 * (§3.1). That is the whole reason this is a tile affordance and not a
 * migration. */
function RenameProject({
  p,
  onClose,
  onDone,
}: {
  p: ProjectCard
  onClose: () => void
  onDone: () => void
}) {
  const [name, setName] = useState(p.name)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  // the name is the thing being edited, so the focus lands there and
  // the window does not take it back (`autoFocus={false}`)
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])
  const save = async () => {
    setBusy(true)
    setErr(null)
    try {
      await apiPatch(`/api/projects/${encodeURIComponent(p.name)}`, { name: name.trim() })
      onDone()
      onClose()
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }
  return (
    <ConfirmWindow
      title="Rename this project"
      subject={p.name}
      width="sm"
      autoFocus={false}
      onClose={onClose}
    >
      <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">
        one identifier — a letter, then letters, digits or underscore. The tasks on this
        shelf keep their names and their folders; only the shelf is renamed.
      </p>
      <input
        ref={inputRef}
        className="mt-3 w-full rounded-md border border-edge bg-bg px-2 py-1.5 font-mono text-xs text-ink focus:border-ink-faint focus:outline-none"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && name.trim() !== '' && !busy) void save()
        }}
      />
      {err && <div className="mt-2 text-xs text-danger">{err}</div>}
      <div className="mt-4 flex items-center justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={busy}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={busy || name.trim() === '' || name.trim() === p.name}
          onClick={() => void save()}
        >
          {busy ? 'Renaming…' : 'Rename'}
        </Button>
      </div>
    </ConfirmWindow>
  )
}

/** Destruction, so it floats (DESIGN.md). No typed-name ceremony: the
 * engine only ever deletes an EMPTY shelf — a populated one is refused
 * (§3.1: deleting it would either strand its tasks or silently take
 * them with it) — so this window's job is to say the count and, when it
 * is not zero, name the way out instead of offering a button that the
 * engine would answer 409 to. */
function DeleteProject({
  p,
  onClose,
  onDone,
}: {
  p: ProjectCard
  onClose: () => void
  onDone: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const empty = p.problems === 0
  const remove = async () => {
    setBusy(true)
    setErr(null)
    try {
      await apiDelete(`/api/projects/${encodeURIComponent(p.name)}`)
      onDone()
      onClose()
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String((e as Error).message))
      setBusy(false)
    }
  }
  return (
    <ConfirmWindow title={`Delete the ${p.name} shelf?`} width="sm" onClose={onClose}>
      <p className="mt-2 text-xs leading-relaxed text-ink-dim">
        {empty ? (
          <>
            It holds no tasks. The shelf and its description go; nothing else on disk is
            touched.
          </>
        ) : (
          <>
            It still holds{' '}
            <span className="tnum text-ink">
              {p.problems} task{p.problems === 1 ? '' : 's'}
            </span>
            . A shelf is only deleted once it is empty — file them on another shelf, or
            delete them first.
          </>
        )}
      </p>
      {err && <div className="mt-2 text-xs text-danger">{err}</div>}
      <div className="mt-4 flex items-center justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={busy}>
          {empty ? 'Cancel' : 'Close'}
        </Button>
        {empty && (
          <button
            className="cursor-pointer rounded-lg bg-destruct px-3 py-1.5 text-xs font-medium text-starlight transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-50"
            disabled={busy}
            onClick={() => void remove()}
          >
            {busy ? 'Deleting…' : 'Delete'}
          </button>
        )}
      </div>
    </ConfirmWindow>
  )
}

function Tile({ p }: { p: ProjectCard }) {
  return (
    <Link
      to={projectPath(p.name, 'tasks')}
      className={`relative isolate flex h-full min-h-[400px] flex-col overflow-hidden rounded-xl border bg-surface p-6 pt-10 transition-colors duration-150 hover:border-ink-faint ${p.attention > 0 ? 'border-ink-faint' : 'border-edge'}`}
      title={p.last_event ? `last event ${relTime(p.last_event)}` : undefined}
    >
      <ProjectSkyPreview project={p.name} empty={p.problems === 0} />
      <div className="relative flex items-baseline gap-2">
        <span className="min-w-0 flex-1 break-words font-display text-[26px] leading-tight text-ink">
          {p.name}
        </span>
      </div>
      <p className="relative mt-2 mb-4 line-clamp-2 text-[12.5px] leading-relaxed text-ink-dim" title={p.description || undefined}>
        {p.description}
      </p>
      <div className="tnum relative mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 pt-3 text-[11px] text-ink-dim">
        <span>
          {p.problems} task{p.problems === 1 ? '' : 's'}
        </span>
        {p.running > 0 && (
          <span className="flex items-center gap-1.5 text-ink-dim">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            {p.running} running
          </span>
        )}
        {p.attention > 0 && (
          <span className="ml-auto rounded-full bg-ink px-2 py-0.5 text-bg">
            {p.attention} need{p.attention === 1 ? 's' : ''} you
          </span>
        )}
      </div>
    </Link>
  )
}

/** New Project floats: naming a shelf is a task of its own, and the
 * grid behind it is the thing being added to (DESIGN.md — float where
 * the work is genuinely its own task). */
function NewProject({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  // the name field is what the window is for, so it takes the focus
  // and the window stands back (`autoFocus={false}`)
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])
  const create = async () => {
    setBusy(true)
    setErr(null)
    try {
      const r = await apiPost<{ project: string }>('/api/projects', { name, description })
      setOpen(false)
      setName('')
      setDescription('')
      onDone()
      navigate(projectPath(r.project, 'tasks'))
    } catch (e) {
      setErr(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <button
        className="flex min-h-[400px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-edge p-5 text-[12.5px] text-ink-dim transition-colors hover:border-ink-faint hover:bg-surface"
        onClick={() => setOpen(true)}
      >
        <span className="mb-1 text-[18px] leading-none">+</span>
        new project
      </button>
      {open && (
        <ConfirmWindow
          title="New project"
          width="sm"
          autoFocus={false}
          onClose={() => setOpen(false)}
        >
          <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">
            one identifier — a letter, then letters, digits or underscore. It becomes the
            default prefix for the tasks you file here.
          </p>
          <input
            ref={inputRef}
            className="mt-3 w-full rounded-md border border-edge bg-bg px-2 py-1.5 font-mono text-xs text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
            placeholder="Combinatorics"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <textarea
            className="mt-2 h-20 w-full resize-none rounded-md border border-edge bg-bg px-2 py-1.5 text-xs text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
            placeholder="what this shelf is for (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          {err && <div className="mt-2 text-xs text-danger">{err}</div>}
          <div className="mt-4 flex items-center justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={busy || name.trim() === ''}
              onClick={() => void create()}
            >
              {busy ? 'Creating…' : 'Create'}
            </Button>
          </div>
        </ConfirmWindow>
      )}
    </>
  )
}

export default function Projects({ onOpenSettings }: { onOpenSettings: () => void }) {
  const { data, error, refresh } = usePoll<{ projects: ProjectCard[] }>('/api/projects', 5000)
  /** the shelf a floating window is about, and which window it is */
  const [acting, setActing] = useState<{ p: ProjectCard; kind: 'rename' | 'delete' } | null>(
    null,
  )
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<ProjectFilter>('all')
  if (error && !data) return <ErrorState error={error} />
  const projects = data?.projects ?? []
  const visible = visibleProjects(projects, query, filter)
  const filters = [
    ['all', 'All projects', projects.length],
    ['running', 'Running', projects.filter(p => p.running > 0).length],
    ['attention', 'Needs you', projects.filter(p => p.attention > 0).length],
  ] as const
  return (
    <div className="mx-auto max-w-7xl px-8 py-9">
      <header className="mb-9 flex items-center">
        <span className="flex items-center gap-2">
          {MARK}
          <span className="font-display text-[17px] font-medium">Asterism</span>
        </span>
        <div className="ml-auto flex items-center gap-1">
          {/* the same labelled control the Project header wears, so the
              place is named the same way from both doors */}
          <IconButton
            onClick={onOpenSettings}
            label="Settings"
            title="settings — accounts, machine, appearance"
          >
            {GEAR}
          </IconButton>
          <HelpButton />
        </div>
      </header>
      <section className="mb-8 mt-12">
        <h1 className="font-display text-4xl text-ink sm:text-5xl">Your research.</h1>
        <p className="mt-3 text-sm leading-relaxed text-ink-dim">
          A place for each question. Pick up the argument where it stands.
        </p>
      </section>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Filter projects">
          {filters.map(([value, label, count]) => (
            <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}
              className={`cursor-pointer rounded-lg px-3 py-2 text-xs transition-colors ${filter === value ? 'bg-ink text-bg' : 'text-ink-dim hover:bg-surface-2 hover:text-ink'}`}>
              {label}<span className="tnum ml-2 opacity-65">{data ? count : '—'}</span>
            </button>
          ))}
        </div>
        <div className="w-full sm:w-72">
          <CollectionSearch value={query} onChange={setQuery} label="Search projects" placeholder="find a project…" />
        </div>
      </div>
      {error && data && <div role="status" className="mb-4 text-xs text-ink-dim">Updates unavailable — showing the last reading. <button className="cursor-pointer underline" onClick={refresh}>Retry</button></div>}
      {!data ? <p role="status" className="py-12 text-sm text-ink-dim">Loading projects…</p> : <>
      {projects.length === 0 && <p className="mb-6 text-sm text-ink-dim">Start with a project. Its tasks, documents and discussions will live together here.</p>}
      {visible.length === 0 && projects.length > 0 && (
        <div role="status" className="mb-6 rounded-xl border border-edge px-6 py-10">
          <p className="font-display text-2xl">No matching projects.</p>
          <p className="mt-2 text-xs text-ink-dim">Try another name or description, or <button className="cursor-pointer underline" onClick={() => { setQuery(''); setFilter('all') }}>show all projects</button>.</p>
        </div>
      )}
      <div className="grid gap-5 md:grid-cols-2">
        {visible.map((p) => (
          // the tile is a link; its acts are SIBLINGS of the anchor, not
          // children of it — a button inside a link is one element that
          // does two things
          <div key={p.name} className="group relative">
            <Tile p={p} />
            <TileActions
              p={p}
              onRename={() => setActing({ p, kind: 'rename' })}
              onDelete={() => setActing({ p, kind: 'delete' })}
            />
          </div>
        ))}
        <NewProject onDone={refresh} />
      </div>
      </>}
      {acting?.kind === 'rename' && (
        <RenameProject p={acting.p} onClose={() => setActing(null)} onDone={refresh} />
      )}
      {acting?.kind === 'delete' && (
        <DeleteProject p={acting.p} onClose={() => setActing(null)} onDone={refresh} />
      )}
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { relTime } from '../lib/format'
import { projectPath } from '../lib/projectRoute'
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
 * A tile says three things: what this shelf is, how much is on it, and
 * whether it wants the reader. Nothing else earns ink — an empty
 * description leaves an empty line rather than a placeholder, because
 * "no description" is not news. Order is alphabetical and stays that
 * way: a picker whose tiles move between visits cannot be learned.
 */

function Tile({ p }: { p: ProjectCard }) {
  return (
    <Link
      to={projectPath(p.name, 'tasks')}
      className="group flex flex-col rounded-xl border border-edge bg-surface p-5 transition-colors duration-150 hover:border-edge-strong hover:bg-surface-2"
      title={p.last_event ? `last event ${relTime(p.last_event)}` : undefined}
    >
      <div className="flex items-baseline gap-2">
        <span className="min-w-0 flex-1 truncate font-display text-[18px] text-ink">
          {p.name}
        </span>
        {/* the human's move, in the mark that means exactly that
            everywhere else in this console */}
        {p.attention > 0 && (
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full bg-warn"
            title={`${p.attention} task${p.attention === 1 ? '' : 's'} waiting on you`}
          />
        )}
      </div>
      <p className="mt-1.5 min-h-[3.1em] text-[12.5px] leading-relaxed text-ink-dim">
        {p.description}
      </p>
      <div className="tnum mt-4 flex items-center gap-3 text-[11px] text-ink-faint">
        <span>
          {p.problems} task{p.problems === 1 ? '' : 's'}
        </span>
        {p.running > 0 && (
          <span className="flex items-center gap-1.5 text-ink-dim">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            {p.running} running
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
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
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
        className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-edge p-5 text-[12.5px] text-ink-faint transition-colors hover:border-edge-strong hover:text-ink-dim"
        onClick={() => setOpen(true)}
      >
        <span className="mb-1 text-[18px] leading-none">+</span>
        new project
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-bg/70"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-[26rem] rounded-xl border border-edge bg-surface p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="font-display text-[17px] text-ink">New project</div>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">
              one identifier — a letter, then letters, digits or underscore. It becomes
              the default prefix for the tasks you file here.
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
          </div>
        </div>
      )}
    </>
  )
}

export default function Projects() {
  const { data, error, refresh } = usePoll<{ projects: ProjectCard[] }>('/api/projects', 5000)
  if (error && !data) return <ErrorState error={error} />
  const projects = data?.projects ?? []
  return (
    <div className="mx-auto max-w-6xl px-8 py-9">
      <header className="mb-9 flex items-center">
        <span className="flex items-center gap-2">
          {MARK}
          <span className="font-display text-[17px] font-medium">Asterism</span>
        </span>
        <div className="ml-auto flex items-center gap-1">
          <IconButton to="/settings" title="settings — accounts, machine, appearance">
            {GEAR}
          </IconButton>
          <HelpButton />
        </div>
      </header>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((p) => (
          <Tile key={p.name} p={p} />
        ))}
        <NewProject onDone={refresh} />
      </div>
    </div>
  )
}

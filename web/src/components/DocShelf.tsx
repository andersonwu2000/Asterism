import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, apiDelete, apiGet, apiPost, apiPut, apiUpload, usePoll } from '../lib/api'
import { Lean } from '../lib/lean'
import { renderInline, renderProse } from '../lib/prose'
import { frameClass } from '../lib/textFrame'
import { ConfirmWindow } from './ConfirmWindow'
import LeanDoc from './LeanDoc'
import TexDoc from './TexDoc'
import { Button } from './ui'

/*
 * The Project's own shelf, writable (human_interface_design.md §1.2,
 * §3.6). Two sub-roots under `Problems/<project>/_docs/`, and the split
 * is the capability matrix made visible:
 *
 *   user/    the person's. The console writes here and nowhere else.
 *   agent/   what the Assistant produced. Read-only from this side —
 *            a PUT into it would merge two areas whose separation is
 *            the point, and the engine refuses it anyway.
 *
 * The fence lives in `state/project_docs`, so this file never decides
 * what a legal path is: it sends what the person typed and shows the
 * refusal, which names the way out. Every 422 here is a sentence
 * written for the person about the path they wrote.
 *
 * Papers live here too (§3.9, 2026-09-03 — the `#/papers` page and the
 * workspace-global shelf retired): each is a `papers/<id>/` folder with
 * its `paper.pdf`, its extracted `text.md` and its `map.md`, read like
 * any other document. Adding one is the one act that is NOT a document
 * PUT — a paper is extracted, hashed into its content id and given a
 * `meta.json` — so a drop goes to `POST /api/projects/{p}/papers`,
 * which lands it under `user/papers/`.
 */

export interface DocEntry {
  path: string
  kind: 'file' | 'dir'
  size?: number
}

/** One paper on its way onto the shelf. Extraction is real server work,
 * so the strip says which file and how far it got. */
interface UploadItem {
  key: number
  name: string
  status: 'uploading' | 'shelved' | 'already' | 'error'
  detail?: string
}

/* The file column's fold, in two halves — the strip that brings the
 * column back, and the button that puts it away. Both roots of the
 * Documents section wear them, so they are written once here and the
 * state that drives them lives one level up, in Docs.tsx. The shape is
 * the task rail's (ProjectShell): a reading posture, kept. */

export function ClosedColumn({ onOpen }: { onOpen: () => void }) {
  return (
    <div className="shrink-0 border-r border-edge px-2 py-4">
      <button
        onClick={onOpen}
        title="show the file list"
        className="cursor-pointer rounded-md px-1.5 py-1 text-[11px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
      >
        ›
      </button>
    </div>
  )
}

export function HideColumn({ onHide }: { onHide: () => void }) {
  return (
    <button
      onClick={onHide}
      title="hide the file list"
      className="cursor-pointer rounded-md px-1 text-[11px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
    >
      ‹
    </button>
  )
}

const TEXT_EXT = ['.md', '.tex', '.txt', '.lean']
const IMAGE_EXT = ['.png', '.jpg', '.svg']
/** The kinds whose right half is a panel of its own while you write
 * (§1.2-2: 左編輯、右面板) — Lean's Info view, TeX's compiled pdf.
 * `.md` keeps the read/edit toggle: its render is the whole page, not
 * a companion to writing it. */
const SPLIT_EXT = ['.lean', '.tex']

const ext = (p: string): string => {
  const i = p.lastIndexOf('.')
  return i < 0 ? '' : p.slice(i).toLowerCase()
}
const isText = (p: string) => TEXT_EXT.includes(ext(p))
const isImage = (p: string) => IMAGE_EXT.includes(ext(p))
const isUser = (p: string) => p === 'user' || p.startsWith('user/')

const MIME: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.pdf': 'application/pdf',
}

/** A `.tex` file, READ — the Assistant's area, where there is nothing
 * to write and so no compile panel beside it. The file is shown as its
 * own text, line for line, with `$…$` typeset: the half a
 * mathematician actually reads, and no engine needed to show it. */
function TexBody({ content }: { content: string }) {
  return (
    <div className="max-w-[78ch] text-[13px] leading-relaxed text-ink-dim">
      {content.split('\n').map((line, i) =>
        line.trim() === '' ? (
          <div key={i} className="h-3" />
        ) : (
          <div key={i}>{renderInline(line, `t${i}`)}</div>
        ),
      )}
    </div>
  )
}

/** A pdf, shown by the browser's own viewer. It is pointed at the raw
 * document address rather than at a blob built from the base64 payload:
 * a paper runs to tens of megabytes, and a blob cannot answer the range
 * requests the viewer makes to open page one before the rest arrives. */
function PdfBody({ project, path }: { project: string; path: string }) {
  return (
    <iframe
      src={`${docPath(project, path)}?raw=1`}
      title={path}
      className="h-full min-h-[36rem] w-full rounded-xl border border-edge bg-wash"
    />
  )
}

function Body({
  project,
  path,
  content,
  base64,
}: {
  project: string
  path: string
  content?: string
  base64?: string
}) {
  const e = ext(path)
  if (e === '.pdf') return <PdfBody project={project} path={path} />
  if (base64 !== undefined)
    return (
      <img
        src={`data:${MIME[e] ?? 'application/octet-stream'};base64,${base64}`}
        alt={path}
        className="max-w-full rounded-xl border border-edge"
      />
    )
  if (content === undefined) return null
  if (e === '.svg')
    return (
      <img
        src={`data:image/svg+xml;utf8,${encodeURIComponent(content)}`}
        alt={path}
        className="max-w-full rounded-xl border border-edge"
      />
    )
  // Only the Assistant's area reaches this: a `.lean` under `user/`
  // opens in the editor beside its Info panel (§1.2-2).
  if (e === '.lean')
    return (
      <pre className={frameClass({ frame: false, size: 'md', wrap: false })}>
        <Lean code={content} />
      </pre>
    )
  if (e === '.tex') return <TexBody content={content} />
  if (e === '.md')
    return (
      <div className="max-w-[78ch] text-[13px] leading-relaxed text-ink-dim">
        {renderProse(content, { mode: 'document', frontmatter: true })}
      </div>
    )
  return <pre className={frameClass({ frame: false, size: 'md' })}>{content}</pre>
}

/** Irreversible, so it floats (DESIGN.md). The typed-name ceremony
 * belongs to deleting a whole task; a document names itself and asks
 * once. */
function DeleteDoc({
  path,
  onConfirm,
  onCancel,
  busy,
  error,
}: {
  path: string
  onConfirm: () => void
  onCancel: () => void
  busy: boolean
  error: string | null
}) {
  return (
    <ConfirmWindow title="Delete this document?" width="sm" onClose={onCancel}>
      <p className="mt-2 font-mono text-xs break-all text-ink-dim">{path}</p>
      <p className="mt-2 text-xs leading-relaxed text-ink-faint">
        It is removed from disk. Nothing here keeps a copy.
      </p>
      {error && <div className="mt-2 text-xs text-danger">{error}</div>}
      <div className="mt-4 flex items-center justify-end gap-2">
        <Button variant="outline" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <button
          className="cursor-pointer rounded-lg bg-destruct px-3 py-1.5 text-xs font-medium text-starlight transition-opacity hover:opacity-90 disabled:cursor-default disabled:opacity-50"
          disabled={busy}
          onClick={onConfirm}
        >
          {busy ? 'Deleting…' : 'Delete'}
        </button>
      </div>
    </ConfirmWindow>
  )
}

/** One area's rows, indented by their own path depth. The API returns
 * the tree flat and root-relative on purpose — the nesting is in the
 * string, so "which file is open" stays a comparison. */
function AreaRows({
  entries,
  area,
  selected,
  dirty,
  onPick,
}: {
  entries: DocEntry[]
  area: string
  selected: string | null
  dirty: Set<string>
  onPick: (p: string) => void
}) {
  const rows = entries.filter((e) => e.path === area || e.path.startsWith(`${area}/`))
  if (rows.length === 0)
    return (
      <p className="px-4 py-1.5 text-[11px] leading-relaxed text-ink-faint">
        {area === 'user'
          ? 'nothing here yet — “new file” starts one.'
          : 'nothing here yet — the Assistant writes into this one.'}
      </p>
    )
  return (
    <>
      {rows
        .filter((e) => e.path !== area)
        .map((e) => {
          const depth = e.path.split('/').length - 2
          const name = e.path.split('/').pop() ?? e.path
          const on = e.path === selected
          return (
            <button
              key={e.path}
              className={`flex w-full items-baseline gap-1.5 px-4 py-1 text-left font-mono text-xs ${
                on ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:text-ink'
              }`}
              style={{ paddingLeft: `${16 + depth * 12}px` }}
              onClick={() => onPick(e.path)}
              title={e.path}
            >
              {e.kind === 'dir' && (
                <span className="shrink-0 text-ink-faint" aria-hidden>
                  /
                </span>
              )}
              <span className="min-w-0 flex-1 truncate">{name}</span>
              {dirty.has(e.path) && (
                <span
                  className="shrink-0 text-star"
                  title="unsaved changes on this document"
                >
                  ·
                </span>
              )}
            </button>
          )
        })}
    </>
  )
}

export default function DocShelf({
  project,
  columnOpen,
  onToggleColumn,
  onOpenChange,
}: {
  project: string
  /** the file column's fold. ONE column, ONE fold: Docs.tsx owns it
   * for both roots, so switching root cannot change the posture the
   * reader set (until 2026-09-04 only this root could fold at all) */
  columnOpen: boolean
  onToggleColumn: () => void
  /** which document is under the cursor — the Assistant is told, and
   * only the screen above may publish it (one focus, one author) */
  onOpenChange?: (path: string | null) => void
}) {
  const { data: tree, refresh } = usePoll<{ entries: DocEntry[] }>(
    `/api/projects/${encodeURIComponent(project)}/docs`,
    30000,
  )
  const entries = useMemo(() => tree?.entries ?? [], [tree])
  const [selected, setSelected] = useState<string | null>(null)
  const [doc, setDoc] = useState<{
    path: string
    content?: string
    content_base64?: string
  } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  /** per-path edits, so walking the column does not throw work away */
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  /** bumped each time a document lands on disk — a companion panel that
   * compiles the file follows the SAVE, not every keystroke */
  const [savedAt, setSavedAt] = useState(0)
  const [note, setNote] = useState<string | null>(null)
  const [creating, setCreating] = useState<'file' | 'dir' | null>(null)
  const [newName, setNewName] = useState('')
  /** a refusal about the NAME belongs under the name box, not in the
   * header of a document it is not about */
  const [createNote, setCreateNote] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  /** the address being renamed — the whole root-relative path, so the
   * one control both renames and moves (§1.2-3) */
  const [renameTo, setRenameTo] = useState<string | null>(null)
  const [renameNote, setRenameNote] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const renameRef = useRef<HTMLInputElement | null>(null)
  /** papers being shelved — one line each while the extraction runs */
  const [uploads, setUploads] = useState<UploadItem[]>([])
  const seq = useRef(0)
  const paperInput = useRef<HTMLInputElement | null>(null)
  // Counter, not boolean: dragging over child elements fires
  // leave/enter pairs that a boolean would read as "left the area".
  const [dragDepth, setDragDepth] = useState(0)

  const files = useMemo(() => entries.filter((e) => e.kind === 'file'), [entries])
  // the column opens on something rather than an empty frame
  const open = selected ?? files[0]?.path ?? null
  const openIsDir = entries.some((e) => e.path === open && e.kind === 'dir')
  const writable = open !== null && isUser(open) && isText(open)
  /** a document whose companion panel IS the page's right half — it has
   * no read mode to toggle into, because the editor already reads */
  const split = writable && !openIsDir && SPLIT_EXT.includes(ext(open))

  useEffect(() => {
    if (open === null || openIsDir) {
      setDoc(null)
      return
    }
    // A pdf is never read INTO this component: its viewer fetches the
    // raw address itself. Pulling the base64 payload here would be tens
    // of megabytes nothing reads.
    if (ext(open) === '.pdf') {
      setLoadError(null)
      setDoc({ path: open })
      return
    }
    let gone = false
    setLoadError(null)
    apiGet<{ path: string; content?: string; content_base64?: string }>(
      `/api/projects/${encodeURIComponent(project)}/docs/${open
        .split('/')
        .map(encodeURIComponent)
        .join('/')}`,
    )
      .then((d) => !gone && setDoc(d))
      .catch((e) => {
        if (gone) return
        setDoc(null)
        setLoadError(e instanceof ApiError ? e.detail : String((e as Error).message))
      })
    return () => {
      gone = true
    }
  }, [project, open, openIsDir])

  useEffect(() => {
    setEditing(false)
    setNote(null)
    setRenameTo(null)
    setRenameNote(null)
  }, [open])
  useEffect(() => {
    if (renameTo !== null) renameRef.current?.focus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renameTo === null])
  const openChangeRef = useRef(onOpenChange)
  openChangeRef.current = onOpenChange
  useEffect(() => {
    openChangeRef.current?.(open)
  }, [open])
  useEffect(() => {
    if (creating !== null) inputRef.current?.focus()
  }, [creating])

  // a draft is dirty unless it is exactly what is on disk — typing and
  // then undoing must not leave the column claiming unsaved work
  const dirty = useMemo(() => {
    const out = new Set<string>()
    for (const [p, v] of Object.entries(drafts)) {
      if (doc !== null && doc.path === p && v === (doc.content ?? '')) continue
      out.add(p)
    }
    return out
  }, [drafts, doc])

  const body = open !== null && drafts[open] !== undefined ? drafts[open] : doc?.content

  const save = useCallback(async () => {
    if (open === null || body === undefined) return
    setSaving(true)
    setNote(null)
    try {
      await docPut(project, open, { content: body })
      setDrafts((d) => {
        const next = { ...d }
        delete next[open]
        return next
      })
      setDoc((x) => (x === null ? x : { ...x, content: body }))
      setEditing(false)
      setNote('saved')
      setSavedAt((n) => n + 1)
      refresh()
    } catch (e) {
      setNote(e instanceof ApiError ? e.detail : String((e as Error).message))
    } finally {
      setSaving(false)
    }
  }, [project, open, body, refresh])

  const create = async () => {
    const name = newName.trim()
    if (name === '') return
    // a new thing goes inside the folder you are standing in, and
    // under `user/` — the only area this door writes
    const base = open === null ? 'user' : openIsDir ? open : open.split('/').slice(0, -1).join('/')
    const path = `${isUser(base) ? base : 'user'}/${name}`.replace(/\/+/g, '/')
    setCreateNote(null)
    // A dot segment cannot be SENT, whatever the engine would say about
    // it: the URL parser collapses `user/../x` (and `%2e%2e`, which it
    // treats the same) before the request leaves the browser, so the
    // fence would judge a path the person never wrote. This is the
    // console reporting an address it cannot carry — not a second
    // opinion about what the tree accepts.
    if (path.split('/').some((seg) => seg === '.' || seg === '..')) {
      setCreateNote(
        'a name cannot be “.” or “..” — those are folder steps, and the address this ' +
          'console sends cannot carry them. Pick the folder on the left instead.',
      )
      return
    }
    try {
      await docPut(project, path, creating === 'dir' ? { kind: 'dir' } : { content: '' })
      setNewName('')
      setCreating(null)
      setCreateNote(null)
      refresh()
      if (creating === 'file') {
        setSelected(path)
        setEditing(true)
      }
    } catch (e) {
      setCreateNote(e instanceof ApiError ? e.detail : String((e as Error).message))
    }
  }

  /** Rename, or move: the box carries the whole root-relative path, so
   * editing the last segment renames and editing an earlier one moves.
   * The engine owns what a legal path is — a refusal comes back as the
   * sentence it wrote about the path the person typed. */
  const doRename = async () => {
    if (open === null || renameTo === null) return
    const to = renameTo.trim()
    if (to === '' || to === open) {
      setRenameTo(null)
      return
    }
    setRenameNote(null)
    try {
      const r = (await apiPost(docPath(project, open), { to })) as { path: string }
      setDrafts((d) => {
        if (d[open] === undefined) return d
        const next = { ...d }
        next[r.path] = next[open]
        delete next[open]
        return next
      })
      setRenameTo(null)
      setSelected(r.path)
      refresh()
    } catch (e) {
      setRenameNote(e instanceof ApiError ? e.detail : String((e as Error).message))
    }
  }

  /** Shelve papers, sequentially: PDF extraction is real server work,
   * and a strip that fills top-to-bottom reads as progress. Which
   * suffixes are papers stays server-side — one validator, one
   * wording. */
  const shelvePapers = async (files: File[]) => {
    for (const f of files) {
      const key = ++seq.current
      setUploads((u) => [...u, { key, name: f.name, status: 'uploading' }])
      const settle = (patch: Partial<UploadItem>) => {
        setUploads((u) => u.map((x) => (x.key === key ? { ...x, ...patch } : x)))
        // successes clear themselves after a beat; errors stay
        if (patch.status !== 'error')
          window.setTimeout(
            () => setUploads((u) => u.filter((x) => x.key !== key)),
            4000,
          )
      }
      try {
        const r = await apiUpload<{ id: string; already_shelved: boolean }>(
          `/api/projects/${encodeURIComponent(project)}/papers?filename=${encodeURIComponent(f.name)}`,
          f,
        )
        settle({ status: r.already_shelved ? 'already' : 'shelved' })
        refresh()
      } catch (e) {
        settle({
          status: 'error',
          detail: e instanceof ApiError ? e.detail : String((e as Error).message),
        })
      }
    }
  }

  const hasFiles = (e: React.DragEvent) => e.dataTransfer.types.includes('Files')

  const doDelete = async () => {
    if (open === null) return
    setDeleting(true)
    setNote(null)
    try {
      await apiDelete(
        `/api/projects/${encodeURIComponent(project)}/docs/${open
          .split('/')
          .map(encodeURIComponent)
          .join('/')}`,
      )
      setConfirmDelete(false)
      setSelected(null)
      refresh()
    } catch (e) {
      setNote(e instanceof ApiError ? e.detail : String((e as Error).message))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div
      className="relative flex min-h-0 w-full flex-1"
      onDragEnter={(e) => {
        if (!hasFiles(e)) return
        e.preventDefault()
        setDragDepth((d) => d + 1)
      }}
      onDragOver={(e) => {
        if (hasFiles(e)) e.preventDefault()
      }}
      onDragLeave={(e) => {
        if (hasFiles(e)) setDragDepth((d) => Math.max(0, d - 1))
      }}
      onDrop={(e) => {
        if (!hasFiles(e)) return
        e.preventDefault()
        setDragDepth(0)
        void shelvePapers([...e.dataTransfer.files])
      }}
    >
      {dragDepth > 0 && (
        <div className="pointer-events-none absolute inset-3 z-40 flex items-center justify-center rounded-xl border-2 border-dashed border-ink-faint bg-bg/85">
          <div className="text-center">
            <div className="font-display text-[18px] text-ink">Drop to shelve</div>
            <div className="mt-1 text-xs text-ink-faint">.pdf · .md · .txt · .tex</div>
          </div>
        </div>
      )}
      {!columnOpen ? (
        <ClosedColumn onOpen={onToggleColumn} />
      ) : (
      <div className="flex w-72 shrink-0 flex-col overflow-y-auto border-r border-edge py-2">
        <div className="flex items-baseline gap-2 px-4 pt-1 pb-1">
          <span className="text-[10px] font-medium tracking-widest text-ink-faint/70 uppercase">
            user
          </span>
          <span className="ml-auto flex gap-2">
            <button
              className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
              onClick={() => {
                setCreating('file')
                setNewName('')
                setCreateNote(null)
              }}
              title="a new .md / .tex / .txt / .lean document under user/"
            >
              new file
            </button>
            <button
              className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
              onClick={() => {
                setCreating('dir')
                setNewName('')
                setCreateNote(null)
              }}
              title="a new folder under user/"
            >
              folder
            </button>
            <input
              ref={paperInput}
              type="file"
              multiple
              accept=".pdf,.md,.txt,.tex"
              className="hidden"
              onChange={(e) => {
                const files = [...(e.target.files ?? [])]
                e.target.value = '' // re-picking the same file must re-fire
                void shelvePapers(files)
              }}
            />
            <button
              className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
              onClick={() => paperInput.current?.click()}
              title="shelve a paper under user/papers/ — or drop files anywhere on this page"
            >
              paper
            </button>
            <HideColumn onHide={onToggleColumn} />
          </span>
        </div>
        {creating !== null && (
          <div className="px-4 pb-1.5">
            <input
              ref={inputRef}
              className="w-full rounded-md border border-edge bg-bg px-2 py-1 font-mono text-[11px] text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
              placeholder={creating === 'dir' ? 'folder name' : 'name.md'}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void create()
                if (e.key === 'Escape') {
                  setCreating(null)
                  setCreateNote(null)
                }
              }}
            />
            {createNote && (
              <div className="mt-1 text-[11px] leading-relaxed text-warn">{createNote}</div>
            )}
          </div>
        )}
        {/* one line per paper on its way in; a 422 is written for a
            person, so it is shown whole */}
        {uploads.length > 0 && (
          <div className="space-y-0.5 px-4 pb-1.5">
            {uploads.map((u) => (
              <div key={u.key} className="text-[11px] leading-relaxed">
                <span className="font-mono text-ink-dim">{u.name}</span>{' '}
                {u.status === 'uploading' && (
                  <span className="text-ink-faint">shelving…</span>
                )}
                {u.status === 'shelved' && <span className="text-ink-faint">shelved</span>}
                {u.status === 'already' && (
                  <span className="text-ink-faint">already here (same content)</span>
                )}
                {u.status === 'error' && <span className="text-warn">{u.detail}</span>}
              </div>
            ))}
          </div>
        )}
        <AreaRows
          entries={entries}
          area="user"
          selected={open}
          dirty={dirty}
          onPick={setSelected}
        />
        <div className="mt-3 flex items-baseline gap-2 px-4 pt-1 pb-1">
          <span className="text-[10px] font-medium tracking-widest text-ink-faint/70 uppercase">
            agent
          </span>
          <span
            className="text-[10px] text-ink-faint/70"
            title="what the Assistant wrote; the console reads this area and never writes it"
          >
            read-only
          </span>
        </div>
        <AreaRows
          entries={entries}
          area="agent"
          selected={open}
          dirty={dirty}
          onPick={setSelected}
        />
      </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-edge px-4 py-1.5">
          <span className="min-w-0 truncate font-mono text-[11px] text-ink-dim" title={open ?? ''}>
            {open ?? 'nothing open'}
          </span>
          {open !== null && !isUser(open) && (
            <span className="text-[11px] text-ink-faint">the Assistant's — read-only</span>
          )}
          {writable && !split && (
            <span className="ml-2 flex items-center gap-1">
              {(['read', 'edit'] as const).map((m) => (
                <button
                  key={m}
                  className={`cursor-pointer rounded-md px-2 py-0.5 text-[11px] transition-colors ${
                    (m === 'edit') === editing
                      ? 'bg-surface-2 text-ink'
                      : 'text-ink-faint hover:text-ink-dim'
                  }`}
                  aria-pressed={(m === 'edit') === editing}
                  onClick={() => setEditing(m === 'edit')}
                >
                  {m}
                </button>
              ))}
            </span>
          )}
          {writable && dirty.has(open) && (
            <Button variant="ok" size="xs" disabled={saving} onClick={() => void save()}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
          )}
          {note && (
            <span
              className={`min-w-0 flex-1 truncate text-[11px] ${
                note === 'saved' ? 'text-ink-faint' : 'text-warn'
              }`}
            >
              {note}
            </span>
          )}
          {open !== null && isUser(open) && (
            <span className="ml-auto flex items-center gap-3">
              <button
                className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
                onClick={() => {
                  setRenameTo(open)
                  setRenameNote(null)
                }}
                title="rename it, or move it by editing the folders in its path"
              >
                rename…
              </button>
              <button
                className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
                onClick={() => setConfirmDelete(true)}
              >
                delete…
              </button>
            </span>
          )}
        </div>
        {renameTo !== null && (
          <div className="shrink-0 border-b border-edge px-4 py-1.5">
            <input
              ref={renameRef}
              className="w-full max-w-lg rounded-md border border-edge bg-bg px-2 py-1 font-mono text-[11px] text-ink focus:border-ink-faint focus:outline-none"
              value={renameTo}
              spellCheck={false}
              onChange={(e) => setRenameTo(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void doRename()
                if (e.key === 'Escape') {
                  setRenameTo(null)
                  setRenameNote(null)
                }
              }}
            />
            <div
              className={`mt-1 text-[11px] leading-relaxed ${
                renameNote ? 'text-warn' : 'text-ink-faint'
              }`}
            >
              {renameNote ??
                'the whole path — edit the last part to rename, an earlier one to move. Enter saves, Escape cancels.'}
            </div>
          </div>
        )}
        {split && open !== null && doc !== null && body !== undefined ? (
          ext(open) === '.tex' ? (
            <TexDoc
              key={open}
              project={project}
              path={open}
              value={body}
              savedAt={savedAt}
              onChange={(v) => setDrafts((d) => ({ ...d, [open]: v }))}
            />
          ) : (
            <LeanDoc
              key={open}
              value={body}
              onChange={(v) => setDrafts((d) => ({ ...d, [open]: v }))}
            />
          )
        ) : (
        <div className="min-w-0 flex-1 overflow-auto p-4">
          {loadError && <div className="text-xs text-warn">{loadError}</div>}
          {open === null && (
            <p className="text-[11px] leading-relaxed text-ink-faint">
              Nothing on this shelf yet. “new file” starts one under{' '}
              <span className="font-mono">user/</span>; the Assistant writes into{' '}
              <span className="font-mono">agent/</span>.
            </p>
          )}
          {openIsDir && (
            <p className="text-[11px] text-ink-faint">
              a folder — a new file starts inside it.
            </p>
          )}
          {!openIsDir && open !== null && editing && writable ? (
            <textarea
              className="h-full min-h-[24rem] w-full resize-none rounded-xl border border-edge bg-wash p-3 font-mono text-[12px] leading-relaxed text-ink focus:border-ink-faint focus:outline-none"
              value={body ?? ''}
              spellCheck={false}
              onChange={(e) => setDrafts((d) => ({ ...d, [open]: e.target.value }))}
            />
          ) : (
            !openIsDir &&
            doc !== null && (
              <Body
                project={project}
                path={doc.path}
                content={body}
                base64={doc.content_base64}
              />
            )
          )}
          {!openIsDir && open !== null && isImage(open) && doc === null && !loadError && (
            <div className="late-fade text-xs text-ink-faint">loading…</div>
          )}
        </div>
        )}
      </div>
      {confirmDelete && open !== null && (
        <DeleteDoc
          path={open}
          busy={deleting}
          error={note !== null && note !== 'saved' ? note : null}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() => void doDelete()}
        />
      )}
    </div>
  )
}

/** One document's address. The path is encoded segment by segment —
 * a folder separator is structure, not a character to escape. */
function docPath(project: string, path: string): string {
  return `/api/projects/${encodeURIComponent(project)}/docs/${path
    .split('/')
    .map(encodeURIComponent)
    .join('/')}`
}

function docPut(project: string, path: string, body: unknown): Promise<unknown> {
  return apiPut(docPath(project, path), body)
}

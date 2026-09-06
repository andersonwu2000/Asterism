import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, apiDelete, apiPost, apiPut } from '../lib/api'
import { createFolder, moveTargets, railGroups, refKey } from '../lib/docShell'
import type { DocRef, PaperRow, RailGroup, RailGroupId, RailRow } from '../lib/docShell'
import { theoryLine } from '../lib/docShelf'
import type { DocEntry } from '../lib/docShelf'
import { ConfirmWindow } from './ConfirmWindow'
import { PAGE } from './glyphs'
import { Button, Select } from './ui'

/*
 * The Documents rail (docs_tab_spec.md §D): five groups, and ONE
 * grammar for acting on what they hold.
 *
 * The principles the grammar answers to, in the owner's words: one way
 * to do each thing; discoverable without hovering; keyboard and pointer
 * both; the same grammar for a file and a folder; the selection
 * visible; an API refusal shown AT the item it concerns; and the rail
 * saying "read-only" exactly where a person would try.
 *
 * That last one is why the actions strip renders under every selected
 * row, not only the writable ones: a group whose rows cannot be renamed
 * says so in the place the rename would have been, rather than leaving
 * the reader to discover it by absence.
 */

/** One paper on its way onto the shelf. Extraction is real server work,
 * so the strip says which file and how far it got. */
export interface UploadItem {
  key: number
  name: string
  status: 'uploading' | 'shelved' | 'already' | 'error'
  detail?: string
}

/** What each secondary group says when the person tries to act on one
 * of its rows (§D6). One short sentence, at the item. */
const READ_ONLY: Record<RailGroupId, string | null> = {
  yours: null,
  papers: 'read-only — a paper. Removing one is not offered here yet.',
  agent: "read-only — the machine's",
  engine: "read-only — the engine's",
  proofs: "read-only — the engine's",
}

/** What a group with nothing in it says. */
const EMPTY: Record<RailGroupId, string> = {
  yours: 'nothing here yet — “+ file” starts one.',
  papers: 'no papers yet — drop one anywhere on this page.',
  agent: 'nothing here yet — the theory layer writes into this one.',
  engine: 'this task has written nothing yet.',
  proofs: 'no proofs on this task yet.',
}

/** A group's fold, remembered — a reading posture, like the column's.
 * Secondary groups start folded; `yours` is the tab's centre of gravity
 * and starts open (§D2). */
const foldKey = (id: RailGroupId): string => `asterism.docRail.${id}`

function foldedAtFirst(g: RailGroup): boolean {
  const held = localStorage.getItem(foldKey(g.id))
  if (held !== null) return held === '1'
  return g.secondary
}

/* The rail's flattened reading order. Headers are items too — §D10 asks
 * ArrowUp/Down to walk them and ArrowLeft/Right to fold them, so they
 * cannot be outside the roving tabindex. */
type Item =
  | { kind: 'header'; group: RailGroup }
  | { kind: 'row'; group: RailGroup; row: RailRow }

export default function DocRail({
  project,
  entries,
  papers,
  task,
  tasks,
  taskFiles,
  open,
  dirty,
  uploads,
  onOpen,
  onRefresh,
  onTask,
  onShelve,
  onHide,
  onCreated,
  onRenamed,
  onDeleted,
}: {
  project: string
  entries: DocEntry[]
  papers: PaperRow[]
  task: string | null
  tasks: string[]
  taskFiles: { problem_files: string[]; proof_files: string[]; hasReport: boolean } | null
  open: DocRef | null
  /** root-relative paths holding unsaved writing */
  dirty: ReadonlySet<string>
  uploads: UploadItem[]
  onOpen: (ref: DocRef) => void
  onRefresh: () => void
  onTask: (task: string) => void
  onShelve: (files: File[]) => void
  onHide: () => void
  /** a new thing landed — a file opens with the caret already in it */
  onCreated: (ref: DocRef) => void
  /** a path moved — the screen re-keys its draft and follows it */
  onRenamed: (from: string, to: string) => void
  onDeleted: (path: string, next: DocRef | null) => void
}) {
  const [query, setQuery] = useState('')
  const groups = useMemo(
    () => railGroups({ entries, papers, task, taskFiles, query }),
    [entries, papers, task, taskFiles, query],
  )
  const [folded, setFolded] = useState<Record<string, boolean>>({})
  const [closedDirs, setClosedDirs] = useState<Set<string>>(() => new Set())
  const [focusAt, setFocusAt] = useState(0)
  const listRef = useRef<HTMLDivElement | null>(null)

  // a group's default fold is read once per group, so a group that
  // appears later (the engine group, when its task answers) still
  // starts where the reader left it
  useEffect(() => {
    setFolded((f) => {
      let next = f
      for (const g of groups)
        if (next[g.id] === undefined) next = { ...next, [g.id]: foldedAtFirst(g) }
      return next
    })
  }, [groups])

  // §D3 / §B4-6: a filter is a question about the whole shelf, so
  // nothing stays folded while one is running
  const filtering = query.trim() !== ''
  const isFolded = (g: RailGroup) => !filtering && (folded[g.id] ?? g.secondary)
  const hidden = useCallback(
    (row: RailRow) =>
      !filtering &&
      [...closedDirs].some((d) => row.ref.path.startsWith(`${d}/`)),
    [closedDirs, filtering],
  )

  /* ---- the operations' own state (§D5-D9) ------------------------ */

  const [creating, setCreating] = useState<'file' | 'dir' | null>(null)
  const [newName, setNewName] = useState('')
  const [createNote, setCreateNote] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [renameName, setRenameName] = useState('')
  const [rowNote, setRowNote] = useState<string | null>(null)
  /* what "show in Explorer" came to, at the row it was asked from. A
   * window that opened says nothing (the settled norm earns no ink);
   * a caller the engine will not open a window for — a browser on
   * another machine, a platform with no file manager — gets the
   * absolute path to copy, which is the same answer either way. */
  const [revealed, setRevealed] = useState<{ path: string; where: string } | null>(
    null,
  )
  const [moving, setMoving] = useState<string | null>(null)
  const [moveAt, setMoveAt] = useState(0)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteNote, setDeleteNote] = useState<string | null>(null)
  const createRef = useRef<HTMLInputElement | null>(null)
  const renameRef = useRef<HTMLInputElement | null>(null)
  const paperInput = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (creating !== null) createRef.current?.focus()
  }, [creating])
  useEffect(() => {
    if (renaming !== null) renameRef.current?.focus()
  }, [renaming])
  // walking to another row abandons whatever was half-typed on the old
  // one: an inline input belongs to ITS row and nothing else
  const openKey = open === null ? '' : refKey(open)
  useEffect(() => {
    setRenaming(null)
    setMoving(null)
    setRowNote(null)
  }, [openKey])

  const openIsDir = useMemo(
    () =>
      open !== null &&
      open.kind === 'doc' &&
      entries.some((e) => e.path === open.path && e.kind === 'dir'),
    [entries, open],
  )
  const target = createFolder(open, openIsDir)

  const docUrl = (path: string) =>
    `/api/projects/${encodeURIComponent(project)}/docs/${path
      .split('/')
      .map(encodeURIComponent)
      .join('/')}`
  const refusal = (e: unknown) =>
    e instanceof ApiError ? e.detail : String((e as Error).message)

  const create = async () => {
    const name = newName.trim()
    if (name === '') return
    const path = `${target}/${name}`.replace(/\/+/g, '/')
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
      await apiPut(
        docUrl(path),
        creating === 'dir' ? { kind: 'dir' } : { content: '', create: true },
      )
      setCreating(null)
      setNewName('')
      onRefresh()
      // a folder becomes the current one; a file opens in the editor
      if (creating === 'dir') onOpen({ kind: 'doc', path })
      else onCreated({ kind: 'doc', path })
    } catch (e) {
      setCreateNote(refusal(e))
    }
  }

  /* The one act offered on EVERY row, read-only ones included: asking
   * where a file is is not writing to it, and "where is this pdf?" is
   * asked most often about the rows the console will not let you edit.
   * Only a docs-root row can be asked — the engine's own files are
   * addressed through a different root and the endpoint does not take
   * them (`Tooling/serve/docs_api.py`). */
  const reveal = async (row: RailRow) => {
    setRowNote(null)
    setRevealed(null)
    try {
      const r = (await apiPost('/api/docs/reveal', {
        project,
        path: row.ref.path,
      })) as { path: string; revealed: boolean; detail?: string }
      if (!r.revealed)
        setRevealed({ path: r.path, where: r.detail ?? 'here is the path instead' })
    } catch (e) {
      setRowNote(refusal(e))
    }
  }

  const rename = async (from: string) => {
    const name = renameName.trim()
    const parent = from.split('/').slice(0, -1).join('/')
    const to = `${parent}/${name}`.replace(/\/+/g, '/')
    if (name === '' || to === from) {
      setRenaming(null)
      return
    }
    setRowNote(null)
    try {
      const r = (await apiPost(docUrl(from), { to })) as { path: string }
      setRenaming(null)
      onRenamed(from, r.path)
      onRefresh()
    } catch (e) {
      setRowNote(refusal(e))
    }
  }

  const move = async (from: string, folder: string) => {
    const to = `${folder}/${from.split('/').pop()}`.replace(/\/+/g, '/')
    setRowNote(null)
    try {
      const r = (await apiPost(docUrl(from), { to })) as { path: string }
      setMoving(null)
      onRenamed(from, r.path)
      onRefresh()
    } catch (e) {
      setRowNote(refusal(e))
    }
  }

  /** The row the selection lands on after a delete: the next one in
   * `yours`, or the one before it when the deleted row was last. */
  const neighbourOf = (path: string): DocRef | null => {
    const rows = groups.find((g) => g.id === 'yours')?.rows ?? []
    const i = rows.findIndex((r) => r.ref.path === path)
    if (i < 0) return null
    return (rows[i + 1] ?? rows[i - 1])?.ref ?? null
  }

  const remove = async (path: string) => {
    setDeleteBusy(true)
    setDeleteNote(null)
    try {
      const next = neighbourOf(path)
      await apiDelete(docUrl(path))
      setDeleting(null)
      onDeleted(path, next)
      onRefresh()
    } catch (e) {
      setDeleteNote(refusal(e))
    } finally {
      setDeleteBusy(false)
    }
  }

  /* ---- the flattened tree, and the keyboard on it (§D10) --------- */

  const items = useMemo(() => {
    const out: Item[] = []
    for (const g of groups) {
      out.push({ kind: 'header', group: g })
      if (isFolded(g)) continue
      for (const row of g.rows) if (!hidden(row)) out.push({ kind: 'row', group: g, row })
    }
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groups, folded, closedDirs, filtering, hidden])

  /* Roving tabindex over the flattened tree. The DOM is addressed by
   * `data-at` rather than by the order the query returns: a row being
   * renamed swaps its button for an input, and an index into the
   * remaining buttons would then move the focus to the WRONG row. */
  const focusRow = (i: number) => {
    const n = items.length
    if (n === 0) return
    const at = ((i % n) + n) % n
    setFocusAt(at)
    listRef.current?.querySelector<HTMLElement>(`[data-at="${at}"]`)?.focus()
  }

  const toggleDir = (path: string, want?: boolean) =>
    setClosedDirs((s) => {
      const next = new Set(s)
      const closed = next.has(path)
      if (want === undefined ? closed : want) next.delete(path)
      else next.add(path)
      return next
    })

  const setFold = (id: RailGroupId, v: boolean) => {
    localStorage.setItem(foldKey(id), v ? '1' : '0')
    setFolded((f) => ({ ...f, [id]: v }))
  }

  const onTreeKey = (e: React.KeyboardEvent, i: number, item: Item) => {
    const row = item.kind === 'row' ? item.row : null
    const own = row !== null && item.group.id === 'yours'
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      focusRow(i + 1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      focusRow(i - 1)
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      const wantOpen = e.key === 'ArrowRight'
      if (item.kind === 'header') {
        e.preventDefault()
        setFold(item.group.id, !wantOpen)
      } else if (row!.kind === 'dir') {
        e.preventDefault()
        toggleDir(row!.ref.path, wantOpen)
      }
    } else if (e.key === 'Enter' && row !== null) {
      e.preventDefault()
      onOpen(row.ref)
    } else if (row !== null && row.ref.kind === 'doc' && e.key === 'e') {
      e.preventDefault()
      void reveal(row)
    } else if (own && e.key === 'F2') {
      e.preventDefault()
      startRename(row!)
    } else if (own && e.key === 'm') {
      e.preventDefault()
      startMove(row!)
    } else if (own && e.key === 'Delete') {
      e.preventDefault()
      setDeleting(row!.ref.path)
      setDeleteNote(null)
    } else if (own && (e.key === 'n' || e.key === 'N')) {
      e.preventDefault()
      startCreate(e.key === 'n' ? 'file' : 'dir')
    }
  }

  const startCreate = (kind: 'file' | 'dir') => {
    // the name box lives IN the tree at the place the thing will
    // appear, so the group has to be open for it to be seen at all
    setFold('yours', false)
    setCreating(kind)
    setNewName('')
    setCreateNote(null)
  }
  const startRename = (row: RailRow) => {
    setMoving(null)
    setRowNote(null)
    setRenaming(row.ref.path)
    setRenameName(row.ref.path.split('/').pop() ?? '')
  }
  const startMove = (row: RailRow) => {
    setRenaming(null)
    setRowNote(null)
    setMoving(row.ref.path)
    setMoveAt(0)
  }

  /* ---- drawing ---------------------------------------------------- */

  let index = -1
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-edge">
      <div className="flex shrink-0 items-center gap-2 px-3 py-2">
        <input
          className="min-w-0 flex-1 rounded-md border border-edge bg-bg px-2 py-1 text-[11px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
          placeholder="find by name"
          value={query}
          spellCheck={false}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setQuery('')
          }}
        />
        <button
          onClick={onHide}
          title="hide the file list"
          className="shrink-0 cursor-pointer rounded-md px-1 text-[11px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
        >
          ‹
        </button>
      </div>
      <div
        ref={listRef}
        role="tree"
        aria-label="documents"
        className="min-h-0 flex-1 overflow-y-auto pb-4"
      >
        {groups.map((g) => {
          const gi = ++index
          const gFolded = isFolded(g)
          return (
            <div key={g.id}>
              <div className="mt-2 flex items-baseline gap-2 px-3 pb-1">
                <button
                  data-at={gi}
                  role="treeitem"
                  aria-expanded={!gFolded}
                  tabIndex={gi === focusAt ? 0 : -1}
                  className="cursor-pointer text-[10px] font-medium tracking-widest text-ink-faint/70 uppercase transition-colors hover:text-ink-dim"
                  onClick={() => setFold(g.id, !gFolded)}
                  onFocus={() => setFocusAt(gi)}
                  onKeyDown={(e) => onTreeKey(e, gi, { kind: 'header', group: g })}
                >
                  <span aria-hidden className="mr-1">
                    {gFolded ? '›' : '⌄'}
                  </span>
                  {g.label} · {g.count}
                </button>
                {g.id === 'yours' && (
                  <span className="ml-auto flex gap-2">
                    <button
                      className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
                      onClick={() => startCreate('file')}
                      title={`a new document in ${target}/`}
                    >
                      + file
                    </button>
                    <button
                      className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
                      onClick={() => startCreate('dir')}
                      title={`a new folder in ${target}/`}
                    >
                      + folder
                    </button>
                  </span>
                )}
                {g.id === 'papers' && (
                  <span className="ml-auto">
                    <input
                      ref={paperInput}
                      type="file"
                      multiple
                      accept=".pdf,.md,.txt,.tex"
                      className="hidden"
                      onChange={(e) => {
                        const files = [...(e.target.files ?? [])]
                        e.target.value = '' // re-picking the same file must re-fire
                        onShelve(files)
                      }}
                    />
                    <button
                      className="cursor-pointer text-[11px] text-ink-faint transition-colors hover:text-ink"
                      onClick={() => paperInput.current?.click()}
                      title="shelve a paper — or drop files anywhere on this page"
                    >
                      + paper
                    </button>
                  </span>
                )}
                {g.id === 'engine' && tasks.length > 1 && task !== null && (
                  <Select
                    className="ml-auto w-36"
                    value={task}
                    onChange={(e) => onTask(e.target.value)}
                    title="whose writing this lists"
                  >
                    {tasks.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </Select>
                )}
              </div>
              {g.id === 'papers' && uploads.length > 0 && (
                <div className="space-y-0.5 px-4 pb-1.5">
                  {uploads.map((u) => (
                    <div key={u.key} className="text-[11px] leading-relaxed">
                      <span className="font-mono text-ink-dim">{u.name}</span>{' '}
                      {u.status === 'uploading' && (
                        <span className="text-ink-faint">shelving…</span>
                      )}
                      {u.status === 'shelved' && (
                        <span className="text-ink-faint">shelved</span>
                      )}
                      {u.status === 'already' && (
                        <span className="text-ink-faint">already here (same content)</span>
                      )}
                      {u.status === 'error' && <span className="text-warn">{u.detail}</span>}
                    </div>
                  ))}
                </div>
              )}
              {!gFolded && g.id === 'yours' && creating !== null && target === 'user' && (
                <CreateRow
                  inputRef={createRef}
                  kind={creating}
                  depth={0}
                  where={target}
                  value={newName}
                  note={createNote}
                  onChange={setNewName}
                  onSubmit={() => void create()}
                  onCancel={() => setCreating(null)}
                />
              )}
              {!gFolded && g.rows.length === 0 && (
                <p className="px-4 py-1 text-[11px] leading-relaxed text-ink-faint">
                  {EMPTY[g.id]}
                </p>
              )}
              {!gFolded &&
                g.rows.map((row) => {
                  if (hidden(row)) return null
                  const i = ++index
                  const on = open !== null && refKey(open) === refKey(row.ref)
                  const closed = closedDirs.has(row.ref.path)
                  return (
                    <div key={refKey(row.ref)}>
                      {renaming === row.ref.path ? (
                        <div
                          className="px-4 py-0.5"
                          style={{ paddingLeft: `${16 + row.depth * 12}px` }}
                        >
                          <input
                            ref={renameRef}
                            className="w-full rounded-md border border-edge bg-bg px-2 py-1 font-mono text-[11px] text-ink focus:border-ink-faint focus:outline-none"
                            value={renameName}
                            spellCheck={false}
                            onChange={(e) => setRenameName(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') void rename(row.ref.path)
                              if (e.key === 'Escape') setRenaming(null)
                            }}
                          />
                        </div>
                      ) : (
                        <button
                          data-at={i}
                          role="treeitem"
                          aria-selected={on}
                          aria-expanded={row.kind === 'dir' ? !closed : undefined}
                          tabIndex={i === focusAt ? 0 : -1}
                          className={`group relative flex w-full items-baseline gap-1.5 px-4 py-1 text-left font-mono text-xs ${
                            on ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:text-ink'
                          }`}
                          style={{ paddingLeft: `${16 + row.depth * 12}px` }}
                          onFocus={() => setFocusAt(i)}
                          onKeyDown={(e) => onTreeKey(e, i, { kind: 'row', group: g, row })}
                          onClick={() => onOpen(row.ref)}
                          title={
                            row.theory
                              ? [row.theory.objective, ...row.theory.verdict].join('\n')
                              : row.ref.path
                          }
                        >
                          {on && (
                            <span className="absolute top-1 bottom-1 left-1 w-0.5 rounded-full bg-star" />
                          )}
                          {row.kind === 'dir' && (
                            <span
                              className="shrink-0 cursor-pointer text-ink-faint"
                              role="presentation"
                              onClick={(e) => {
                                // §D4: the chevron folds WITHOUT selecting
                                e.stopPropagation()
                                toggleDir(row.ref.path)
                              }}
                            >
                              {closed ? '›' : '⌄'}
                            </span>
                          )}
                          {row.theory && (
                            <span className="shrink-0 text-ink-faint" aria-hidden>
                              {PAGE}
                            </span>
                          )}
                          <span className="min-w-0 flex-1">
                            <span className="block truncate">{row.name}</span>
                            {row.theory && (
                              <span className="tnum block truncate text-[10px] text-ink-faint">
                                {theoryLine(row.theory)}
                              </span>
                            )}
                          </span>
                          {dirty.has(row.ref.path) && (
                            <span
                              className="shrink-0 text-star"
                              title="unsaved changes on this document"
                            >
                              ·
                            </span>
                          )}
                        </button>
                      )}
                      {on && (
                        <ActionStrip
                          group={g}
                          depth={row.depth}
                          note={rowNote}
                          revealed={revealed}
                          onReveal={
                            row.ref.kind === 'doc' ? () => void reveal(row) : null
                          }
                          onRename={() => startRename(row)}
                          onMove={() => startMove(row)}
                          onDelete={() => {
                            setDeleting(row.ref.path)
                            setDeleteNote(null)
                          }}
                        />
                      )}
                      {moving === row.ref.path && (
                        <MovePicker
                          folders={moveTargets(entries, row.ref.path, row.kind)}
                          at={moveAt}
                          depth={row.depth}
                          onAt={setMoveAt}
                          onPick={(f) => void move(row.ref.path, f)}
                          onCancel={() => setMoving(null)}
                        />
                      )}
                      {g.id === 'yours' &&
                        creating !== null &&
                        target === row.ref.path && (
                          <CreateRow
                            inputRef={createRef}
                            kind={creating}
                            depth={row.depth + 1}
                            where={target}
                            value={newName}
                            note={createNote}
                            onChange={setNewName}
                            onSubmit={() => void create()}
                            onCancel={() => setCreating(null)}
                          />
                        )}
                    </div>
                  )
                })}
            </div>
          )
        })}
      </div>
      {deleting !== null && (
        <DeleteDoc
          path={deleting}
          dirty={dirty.has(deleting)}
          busy={deleteBusy}
          error={deleteNote}
          onCancel={() => setDeleting(null)}
          onConfirm={() => void remove(deleting)}
        />
      )}
    </aside>
  )
}

/** The inline creation row (§D5): a name box where the thing will be,
 * one line saying which folder that is, and the refusal under it. */
function CreateRow({
  inputRef,
  kind,
  depth,
  where,
  value,
  note,
  onChange,
  onSubmit,
  onCancel,
}: {
  inputRef: React.RefObject<HTMLInputElement | null>
  kind: 'file' | 'dir'
  depth: number
  where: string
  value: string
  note: string | null
  onChange: (v: string) => void
  onSubmit: () => void
  onCancel: () => void
}) {
  return (
    <div className="py-1 pr-4" style={{ paddingLeft: `${16 + depth * 12}px` }}>
      <div className="mb-0.5 font-mono text-[10px] text-ink-faint">in {where}/</div>
      <input
        ref={inputRef}
        className="w-full rounded-md border border-edge bg-bg px-2 py-1 font-mono text-[11px] text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
        placeholder={kind === 'dir' ? 'folder name' : 'name.md'}
        value={value}
        spellCheck={false}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onSubmit()
          if (e.key === 'Escape') onCancel()
        }}
      />
      {note !== null && (
        <div className="mt-1 text-[11px] leading-relaxed text-warn">{note}</div>
      )}
    </div>
  )
}

/** What may be done to the selected row — or the sentence saying why
 * nothing may (§D6). The ONLY place these acts live. */
function ActionStrip({
  group,
  depth,
  note,
  revealed,
  onReveal,
  onRename,
  onMove,
  onDelete,
}: {
  group: RailGroup
  depth: number
  note: string | null
  /** where the file is, when no window could be opened onto it */
  revealed: { path: string; where: string } | null
  /** null where this row is not a docs-root file — the engine's own
   * writing is addressed through another root, which this door does
   * not take */
  onReveal: (() => void) | null
  onRename: () => void
  onMove: () => void
  onDelete: () => void
}) {
  const refuse = READ_ONLY[group.id]
  return (
    <div
      className="pr-4 pb-1 text-[11px] text-ink-faint"
      style={{ paddingLeft: `${16 + depth * 12}px` }}
    >
      {refuse !== null ? (
        <span className="flex flex-wrap gap-2">
          <span>{refuse}</span>
          {onReveal !== null && (
            <>
              <span aria-hidden>·</span>
              <RevealButton onReveal={onReveal} />
            </>
          )}
        </span>
      ) : (
        <span className="flex flex-wrap gap-2">
          <button
            className="cursor-pointer transition-colors hover:text-ink"
            onClick={onRename}
            title="F2"
          >
            rename
          </button>
          <span aria-hidden>·</span>
          <button
            className="cursor-pointer transition-colors hover:text-ink"
            onClick={onMove}
            title="m"
          >
            move
          </button>
          <span aria-hidden>·</span>
          <button
            className="cursor-pointer transition-colors hover:text-ink"
            onClick={onDelete}
            title="Delete"
          >
            delete
          </button>
          {onReveal !== null && (
            <>
              <span aria-hidden>·</span>
              <RevealButton onReveal={onReveal} />
            </>
          )}
        </span>
      )}
      {revealed !== null && <RevealedPath at={revealed} />}
      {note !== null && <div className="mt-1 leading-relaxed text-warn">{note}</div>}
    </div>
  )
}

function RevealButton({ onReveal }: { onReveal: () => void }) {
  return (
    <button
      className="cursor-pointer transition-colors hover:text-ink"
      onClick={onReveal}
      title="e — open the folder it is in, with the file selected"
    >
      show in Explorer
    </button>
  )
}

/** No window opened, so the path is the answer — and a path a person
 * has to retype is not one they were given (DESIGN.md: a refusal sits
 * where the act would have been). */
function RevealedPath({ at }: { at: { path: string; where: string } }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="mt-1 leading-relaxed">
      <div>{at.where}</div>
      <div className="mt-0.5 flex items-baseline gap-2">
        <code className="min-w-0 truncate font-mono text-ink-dim" title={at.path}>
          {at.path}
        </code>
        <button
          className="shrink-0 cursor-pointer transition-colors hover:text-ink"
          onClick={() => {
            void navigator.clipboard?.writeText(at.path)
            setCopied(true)
          }}
        >
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
    </div>
  )
}

/** The strip that brings the column back. Its state lives in the
 * screen: the column is ONE column, whichever group is being read. */
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

/** Where a thing may go (§D8). An inline list, not a drag: dragging is
 * a second way to do one act, and this rail has one way for each. */
function MovePicker({
  folders,
  at,
  depth,
  onAt,
  onPick,
  onCancel,
}: {
  folders: string[]
  at: number
  depth: number
  onAt: (i: number) => void
  onPick: (folder: string) => void
  onCancel: () => void
}) {
  const boxRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    boxRef.current?.focus()
  }, [])
  if (folders.length === 0)
    return (
      <div
        className="pr-4 pb-1 text-[11px] text-ink-faint"
        style={{ paddingLeft: `${16 + depth * 12}px` }}
      >
        nowhere else to put it — “+ folder” makes somewhere.
      </div>
    )
  return (
    <div
      ref={boxRef}
      tabIndex={-1}
      /* the control rung of DESIGN.md's radius ladder: this is the
         chooser a `Select` would have been, inlined so the refusal can
         land under the row it concerns */
      className="mr-3 mb-1 ml-4 rounded-lg border border-edge bg-wash py-1 focus:outline-none"
      onKeyDown={(e) => {
        if (e.key === 'ArrowDown') {
          e.preventDefault()
          onAt(Math.min(at + 1, folders.length - 1))
        } else if (e.key === 'ArrowUp') {
          e.preventDefault()
          onAt(Math.max(at - 1, 0))
        } else if (e.key === 'Enter') {
          e.preventDefault()
          onPick(folders[at])
        } else if (e.key === 'Escape') {
          e.preventDefault()
          onCancel()
        }
      }}
    >
      {folders.map((f, i) => (
        <button
          key={f}
          className={`block w-full truncate px-2 py-0.5 text-left font-mono text-[11px] ${
            i === at ? 'bg-surface-2 text-ink' : 'text-ink-dim hover:text-ink'
          }`}
          style={{ paddingLeft: `${8 + (f.split('/').length - 1) * 10}px` }}
          onMouseEnter={() => onAt(i)}
          onClick={() => onPick(f)}
          title={f}
        >
          {f}
        </button>
      ))}
    </div>
  )
}

/** Irreversible, so it floats (DESIGN.md). The typed-name ceremony
 * belongs to deleting a whole task; a document names itself and asks
 * once. */
function DeleteDoc({
  path,
  dirty,
  onConfirm,
  onCancel,
  busy,
  error,
}: {
  path: string
  dirty: boolean
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
        {dirty && ' Its unsaved changes go with it.'}
      </p>
      {error !== null && <div className="mt-2 text-xs text-warn">{error}</div>}
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

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, apiGet, apiPut, apiUpload, usePoll } from '../lib/api'
import { dropDraft, renameDraft, setDraft, unsavedGuard, useDrafts } from '../lib/docDrafts'
import {
  defaultView,
  docAddress,
  editable,
  panelFor,
  parseDocAddress,
  refKey,
} from '../lib/docShell'
import type { DocRef, DocView, PaperRow } from '../lib/docShell'
import type { DocEntry } from '../lib/docShelf'
import { usePublishFocus } from '../lib/focus'
import { replace } from '../lib/router'
import DocRail, { ClosedColumn } from '../components/DocRail'
import type { UploadItem } from '../components/DocRail'
import DocShell from '../components/DocShell'
import type { Conflict } from '../components/DocShell'
import type { PaperShelfItem, ProblemDetail } from '../lib/types'

/*
 * Documents (human_interface_design.md §1.2 + §3.6; the 2026-09-04
 * rewrite in docs_tab_spec.md).
 *
 * The tab's centre of gravity is the PERSON's own documents and the
 * writing of them. What the framework produced — the papers on the
 * shelf, what the Assistant wrote, what the engine wrote for a task —
 * is secondary material the same rail reaches, rather than a second
 * root the reader has to switch to. There used to be two roots
 * (`proofs` / `documents`) and a top-level toggle between them, which
 * asked the reader to know which half of the shelf a file was on before
 * they could look for it.
 *
 * This screen owns the three things a rail and a shell must agree on:
 * the ADDRESS (what is open, in the hash, so a link survives being
 * mailed), the DATA (three polls, no more — a task's detail is ~800KB
 * and only the chosen one is asked for), and the unsaved WRITING, which
 * lives in the module-level draft store so that walking the rail never
 * destroys it.
 */

/** Where the column's fold is remembered. Its own key, beside the task
 * rail's — the two columns are different postures on different pages. */
const COLUMN_KEY = 'asterism.docColumnOpen'

const docUrl = (project: string, path: string): string =>
  `/api/projects/${encodeURIComponent(project)}/docs/${path
    .split('/')
    .map(encodeURIComponent)
    .join('/')}`

const taskFileUrl = (task: string, path: string): string =>
  `/api/problems/${encodeURIComponent(task)}/file?path=${encodeURIComponent(path)}`

const refusal = (e: unknown): string =>
  e instanceof ApiError ? e.detail : String((e as Error).message)

/** One document as it came off the wire. `etag` is the sha1 of the
 * bytes (§A1) — the base a save rebases against. */
interface DiskDoc {
  path: string
  content?: string
  content_base64?: string
  etag: string | null
}

export default function Docs({
  project,
  problem,
  tasks,
  path,
}: {
  project: string
  /** the task whose writing the engine group lists, to begin with */
  problem: string | null
  /** the shelf, so that group can be pointed at another task without
   * leaving the section (this section hides the task column — its own
   * column is the files) */
  tasks: string[]
  /** everything after `docs/` in the address */
  path: string[]
}) {
  /* The address SEEDS the selection and the screen owns it after that
   * (the Sky's idiom for the selected star): clicking through files
   * must not fill the reader's history with one entry per file, so the
   * address is kept up to date with `replace`, never `navigate`. */
  const [open, setOpen] = useState<DocRef | null>(() => parseDocAddress(path))
  const [task, setTask] = useState<string | null>(() => {
    const seed = parseDocAddress(path)
    return seed?.kind === 'task' && seed.task !== null ? seed.task : problem
  })
  const [view, setView] = useState<DocView>(() => {
    const seed = parseDocAddress(path)
    return seed === null ? 'split' : defaultView(seed)
  })
  const [columnOpen, setColumnOpen] = useState(
    () => localStorage.getItem(COLUMN_KEY) !== '0',
  )
  const [doc, setDoc] = useState<DiskDoc | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const [saving, setSaving] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [conflict, setConflict] = useState<Conflict | null>(null)
  /** bumped each time a document lands on disk — the TeX panel follows
   * the SAVE, not every keystroke */
  const [savedAt, setSavedAt] = useState(0)
  /** a document just created here opens with the caret already in it */
  const [autoFocus, setAutoFocus] = useState(false)
  const [uploads, setUploads] = useState<UploadItem[]>([])
  const seq = useRef(0)
  // Counter, not boolean: dragging over child elements fires
  // leave/enter pairs that a boolean would read as "left the area".
  const [dragDepth, setDragDepth] = useState(0)

  useEffect(() => {
    localStorage.setItem(COLUMN_KEY, columnOpen ? '1' : '0')
  }, [columnOpen])

  const { data: tree, refresh: refreshTree } = usePoll<{ entries: DocEntry[] }>(
    `/api/projects/${encodeURIComponent(project)}/docs`,
    30000,
  )
  const { data: shelf, refresh: refreshPapers } = usePoll<{ papers: PaperShelfItem[] }>(
    `/api/projects/${encodeURIComponent(project)}/papers`,
    30000,
  )
  // ONLY the chosen task (§C5): a problem detail is ~800KB, and asking
  // for every task on the shelf would move megabytes to draw one list
  const { data: detail } = usePoll<ProblemDetail>(
    task === null ? null : `/api/problems/${encodeURIComponent(task)}`,
    30000,
  )

  const entries = useMemo(() => tree?.entries ?? [], [tree])
  const papers = useMemo<PaperRow[]>(
    () =>
      (shelf?.papers ?? []).map((p) => ({
        id: p.id,
        title: p.title,
        source_name: p.source_name,
        path: p.path,
        area: p.area,
      })),
    [shelf],
  )
  const taskFiles = useMemo(
    () =>
      detail === null
        ? null
        : {
            problem_files: detail.problem_files ?? [],
            proof_files: detail.proof_files,
            // `ingest_report` is the DB's SoT and REPORT.md is its
            // render, so the rail can never offer a report that the
            // task did not write
            hasReport: Boolean((detail.ingest_report ?? '').trim()),
          },
    [detail],
  )

  const drafts = useDrafts(project)
  const dirtyPathSet = useMemo(() => new Set(drafts.keys()), [drafts])
  const openKey = open === null ? '' : refKey(open)
  const openIsDir =
    open !== null &&
    open.kind === 'doc' &&
    entries.some((e) => e.path === open.path && e.kind === 'dir')
  const theory =
    open === null || open.kind !== 'doc'
      ? null
      : (entries.find((e) => e.path === open.path)?.theory ?? null)
  const draft = open === null || open.kind !== 'doc' ? undefined : drafts.get(open.path)
  const text = draft?.text ?? doc?.content
  const isEditable = open !== null && editable(open) && !openIsDir
  const dirty = draft !== undefined

  /* The shelf answers after the first render, so the task the engine
   * group lists cannot be settled by the initial state alone: on the
   * first paint `problem` is null for the same reason an empty shelf's
   * is. Adopt it once, and never again — after that the Select owns it. */
  useEffect(() => {
    if (task === null && problem !== null) setTask(problem)
  }, [task, problem])

  /* A legacy `#/…/docs/proofs/<file>` link named no task — it opened
   * whichever task the shelf defaulted to, silently, on a shelf running
   * eleven of them. The address now carries the task; a link minted
   * before it is resolved here, once, against the shelf's own default. */
  useEffect(() => {
    if (open?.kind === 'task' && open.task === null && task !== null)
      setOpen({ kind: 'task', task, path: open.path })
  }, [open, task])

  /* The address keeps up with what is on screen. `replace` because this
   * is not a MOVE the reader made — Back has to leave the section, not
   * rewind a walk through the rail. */
  useEffect(() => {
    if (open === null) return
    if (open.kind === 'task' && open.task === null) return
    replace(docAddress(project, open))
  }, [project, open])

  /* The open document's bytes. A pdf is never read INTO this screen —
   * its viewer fetches the raw address itself, and the base64 payload
   * would be tens of megabytes nothing reads. */
  useEffect(() => {
    // the PREVIOUS document is dropped first: a screen that swaps its
    // subject must never show the old one's bytes as if they were the
    // new one's (lib/api's `keepPrevious` makes the same ruling)
    setDoc(null)
    setLoadError(null)
    if (open === null || openIsDir) return
    if (panelFor(open.path) === 'viewer') {
      setDoc({ path: open.path, etag: null })
      return
    }
    if (open.kind === 'task' && open.task === null) return
    const url =
      open.kind === 'doc'
        ? docUrl(project, open.path)
        : taskFileUrl(open.task as string, open.path)
    let gone = false
    apiGet<{ path: string; content?: string; content_base64?: string; etag?: string }>(url)
      .then((d) => {
        if (gone) return
        setDoc({
          path: open.path,
          content: d.content,
          content_base64: d.content_base64,
          etag: d.etag ?? null,
        })
      })
      .catch((e) => {
        if (gone) return
        setDoc(null)
        setLoadError(refusal(e))
      })
    return () => {
      gone = true
    }
    // `openKey` is the identity of `open`; the object is rebuilt on
    // every selection and would re-fetch on unrelated renders
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, openKey, openIsDir, reload])

  // a new document is a new question: the view control, the save note
  // and the conflict all belong to the one that was open
  useEffect(() => {
    setNote(null)
    setConflict(null)
    if (open !== null) setView(defaultView(open))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openKey])

  const onChange = useCallback(
    (v: string) => {
      if (open === null || open.kind !== 'doc') return
      // typing and then undoing is not unsaved work — the store holds
      // only what the disk does not have (lib/docDrafts)
      if (doc?.content !== undefined && v === doc.content) {
        dropDraft(project, open.path)
        return
      }
      // the base a save rebases against is the one the DRAFT started
      // from, not whatever the screen holds now: re-reading the file
      // under a live draft must not silently re-base it
      const held = drafts.get(open.path)
      setDraft(
        project,
        open.path,
        v,
        held !== undefined ? held.baseEtag : (doc?.etag ?? null),
      )
    },
    [project, open, doc, drafts],
  )

  /** Write it. `base` carries the sha1 the draft started from, so the
   * engine can refuse to bury bytes this editor never saw (§A2); saving
   * again WITHOUT it is the reader's explicit "keep mine". */
  const save = useCallback(
    async (base: boolean) => {
      if (open === null || open.kind !== 'doc' || text === undefined) return
      setSaving(true)
      setNote(null)
      try {
        const r = await apiPut<{ path: string; etag?: string }>(
          docUrl(project, open.path),
          base && draft?.baseEtag
            ? { content: text, base_etag: draft.baseEtag }
            : { content: text },
        )
        dropDraft(project, open.path)
        setDoc((d) => (d === null ? d : { ...d, content: text, etag: r.etag ?? null }))
        setConflict(null)
        setNote('saved')
        setSavedAt((n) => n + 1)
        refreshTree()
      } catch (e) {
        // a 409 is not a failure to write — it is the disk saying it
        // moved on, and the reader picks which version stands
        if (e instanceof ApiError && e.status === 409) setConflict({ detail: e.detail })
        else setNote(refusal(e))
      } finally {
        setSaving(false)
      }
    },
    [project, open, text, draft, refreshTree],
  )

  /* Ctrl+S saves, and it swallows the key whenever this tab is mounted:
   * the browser's save-page dialog over an editor is never what the
   * keystroke meant. */
  const saveRef = useRef<() => void>(() => {})
  saveRef.current = () => {
    if (isEditable && dirty && !saving) void save(true)
  }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 's') {
        e.preventDefault()
        saveRef.current()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  /* The one honest beforeunload. App.tsx refuses it for a live RUN
   * (owner, 2026-07-18) because the dialog implies unsaved work that
   * does not exist; here the work is real and on this page only. One
   * listener, reading the count through a ref — re-registering on every
   * keystroke leaves a frame with no guard on it. */
  const dirtyCount = useRef(0)
  dirtyCount.current = drafts.size
  useEffect(() => {
    const onUnload = (e: BeforeUnloadEvent) => unsavedGuard(dirtyCount.current, e)
    window.addEventListener('beforeunload', onUnload)
    return () => window.removeEventListener('beforeunload', onUnload)
  }, [])

  /** Shelve papers, sequentially: PDF extraction is real server work,
   * and a strip that fills top-to-bottom reads as progress. Which
   * suffixes are papers stays server-side — one validator, one
   * wording. */
  const shelvePapers = useCallback(
    async (files: File[]) => {
      for (const f of files) {
        const key = ++seq.current
        setUploads((u) => [...u, { key, name: f.name, status: 'uploading' }])
        const settle = (patch: Partial<UploadItem>) => {
          setUploads((u) => u.map((x) => (x.key === key ? { ...x, ...patch } : x)))
          // successes clear themselves after a beat; errors stay
          if (patch.status !== 'error')
            window.setTimeout(() => setUploads((u) => u.filter((x) => x.key !== key)), 4000)
        }
        try {
          const r = await apiUpload<{ id: string; already_shelved: boolean }>(
            `/api/projects/${encodeURIComponent(project)}/papers?filename=${encodeURIComponent(f.name)}`,
            f,
          )
          settle({ status: r.already_shelved ? 'already' : 'shelved' })
          refreshTree()
          refreshPapers()
        } catch (e) {
          settle({ status: 'error', detail: refusal(e) })
        }
      }
    },
    [project, refreshTree, refreshPapers],
  )

  const hasFiles = (e: React.DragEvent) => e.dataTransfer.types.includes('Files')

  /* ONE author for the screen's focus (§1.4-2): the rail hands its
   * selection up rather than publishing beside this, so the two cannot
   * overwrite each other's answer to "what is open". */
  usePublishFocus({
    problem: open?.kind === 'task' ? open.task : null,
    doc_path: open?.kind === 'doc' ? open.path : null,
  })

  return (
    <div
      className="relative flex h-full min-h-0 w-full"
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
      {columnOpen ? (
        <DocRail
          project={project}
          entries={entries}
          papers={papers}
          task={task}
          tasks={tasks}
          taskFiles={taskFiles}
          open={open}
          dirty={dirtyPathSet}
          uploads={uploads}
          onOpen={(ref) => {
            setAutoFocus(false)
            setOpen(ref)
          }}
          onRefresh={() => {
            refreshTree()
            refreshPapers()
          }}
          onTask={(t) => {
            setTask(t)
            // the open file belonged to the task that is no longer
            // listed; keeping it open would say the rail lists it
            setOpen((o) => (o?.kind === 'task' ? null : o))
          }}
          onShelve={(files) => void shelvePapers(files)}
          onHide={() => setColumnOpen(false)}
          onCreated={(ref) => {
            setAutoFocus(true)
            setOpen(ref)
          }}
          onRenamed={(from, to) => {
            renameDraft(project, from, to)
            setOpen((o) =>
              o?.kind === 'doc' && (o.path === from || o.path.startsWith(`${from}/`))
                ? { kind: 'doc', path: to + o.path.slice(from.length) }
                : o,
            )
          }}
          onDeleted={(path, next) => {
            dropDraft(project, path)
            setOpen(next)
          }}
        />
      ) : (
        <ClosedColumn onOpen={() => setColumnOpen(true)} />
      )}
      <DocShell
        project={project}
        open={open}
        isDir={openIsDir}
        theory={theory}
        doc={
          open === null || openIsDir
            ? null
            : {
                text,
                base64: doc?.content_base64,
                error: loadError,
              }
        }
        view={view}
        onView={setView}
        dirty={dirty}
        saving={saving}
        note={note}
        conflict={conflict}
        savedAt={savedAt}
        autoFocus={autoFocus}
        onChange={onChange}
        onSave={() => void save(true)}
        onTakeDisk={() => {
          if (open?.kind === 'doc') dropDraft(project, open.path)
          setConflict(null)
          setNote(null)
          setReload((n) => n + 1)
        }}
        onKeepMine={() => void save(false)}
      />
    </div>
  )
}

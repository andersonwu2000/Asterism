import { agentRows } from './docShelf'
import type { DocEntry, TheoryMeta } from './docShelf'
import { projectPath } from './projectRoute'

/*
 * The Documents tab's address book and its rail's reading of the shelf
 * (docs_tab_spec.md §B; human_interface_design.md §1.2 + §3.6).
 *
 * The tab's centre of gravity is the PERSON's own documents. Everything
 * else on the shelf — the papers, what the Assistant wrote, what the
 * engine wrote for a task — is secondary material the same rail can
 * reach, so one address shape and one row shape carry all of it.
 *
 * These are the parts with a right answer (which panel a file earns,
 * whose writing it is, what order the rail reads in), so they live here
 * and are tested rather than inline in the screen.
 */

/** What the tab can open.
 *
 * Two kinds, because two things exist: a document on the Project's own
 * shelf, and the engine's writing for ONE task. The task is part of the
 * ref rather than screen state — a shelf runs several tasks, and a link
 * that omits which one silently opens the default task's file (that is
 * exactly the bug the Inbox's "read the report" link carried). */
export type DocRef =
  | { kind: 'doc'; path: string }
  | { kind: 'task'; task: string | null; path: string }

/** Identity for a selection comparison or a React key. Two tasks may
 * each have a `REPORT.md`, and so may the shelf. */
export function refKey(ref: DocRef): string {
  return ref.kind === 'doc' ? `doc:${ref.path}` : `task:${ref.task ?? ''}:${ref.path}`
}

/** The address's tail (`ProjectRoute.rest`) read as a ref.
 *
 * Two legacy shapes are still parsed: `shelf/<path…>` and
 * `proofs/<file>` were minted before this rewrite and live in chat
 * answers, bookmarks and the Inbox. `proofs/…` named no task — the
 * screen fills in the shelf's default — which is why the legacy shape
 * maps onto `task: null` rather than being invented a task here. */
export function parseDocAddress(rest: string[]): DocRef | null {
  const head = rest[0]
  if (head === 'user' || head === 'agent')
    return { kind: 'doc', path: rest.join('/') }
  if (head === 'task') {
    const task = rest[1]
    const path = rest.slice(2).join('/')
    if (!task || path === '') return null
    return { kind: 'task', task, path }
  }
  if (head === 'shelf') {
    const path = rest.slice(1).join('/')
    return path === '' ? null : { kind: 'doc', path }
  }
  if (head === 'proofs') {
    const path = rest.slice(1).join('/')
    return path === '' ? null : { kind: 'task', task: null, path }
  }
  return null
}

/** The ref written back as an address, one encoded segment per path
 * step — a folder separator is structure, not a character to escape.
 *
 * A `task: null` ref is not addressable (it is what a legacy link
 * decodes to, before the screen has resolved which task it meant), so
 * it lands on the section itself rather than minting an address that
 * cannot be read back. */
export function docAddress(project: string, ref: DocRef): string {
  const base = projectPath(project, 'docs')
  const tail = ref.path.split('/').map(encodeURIComponent).join('/')
  if (ref.kind === 'doc') return `${base}/${tail}`
  if (ref.task === null) return base
  return `${base}/task/${encodeURIComponent(ref.task)}/${tail}`
}

/** The docs root's directory name under `Problems/<project>/`
 * (`state/project_docs.ROOT_DIRNAME`). The leading underscore is what
 * keeps it from colliding with a task folder. */
const ROOT_DIRNAME = '_docs'

/** A WORKSPACE-relative path, read as a ref this tab can open — or
 * null, because most workspace paths are not documents.
 *
 * The engine writes its documents by their place in the tree
 * (`Problems/<project>/_docs/<area>/…`, state/project_docs.py) and the
 * Timeline's theory rows carry that string; the tab addresses documents
 * root-relative. The translation is one function so a link from the log
 * cannot mint an address the tab reads back as something else — which
 * is why the two areas are checked rather than passed through: an area
 * `parseDocAddress` does not know is an address that does not read back.
 *
 * Backslashes first: the path is written by whichever platform the
 * engine ran on, and serve's own doc listing normalises the same way. */
export function docRefFromWorkspacePath(project: string, path: string): DocRef | null {
  const parts = String(path ?? '').replace(/\\/g, '/').split('/')
  const [problems, proj, docs, area] = parts
  if (problems !== 'Problems' || proj !== project || docs !== ROOT_DIRNAME) return null
  if (area !== 'user' && area !== 'agent') return null
  const rest = parts.slice(4).join('/')
  if (rest === '') return null
  return { kind: 'doc', path: `${area}/${rest}` }
}

/** The right pane a document earns. `none` is a document that is all
 * left pane — plain text, and anything this console has no reading
 * for. */
export type DocPanel = 'render' | 'pdf-render' | 'info' | 'none' | 'viewer' | 'image'

/** Which editor a writable document earns.
 *
 * The console has exactly two tokenizers — `lib/lean` and the markdown
 * painter in `lib/markdown` — and the Documents tab used neither: every
 * file the person could edit got a bare textarea, while the task page's
 * own markdown was coloured all along (owner, 2026-09-06). The mapping
 * is by LANGUAGE, not by "colour everything": a painter that does not
 * know the language paints it wrong, and `#` opens no heading in TeX
 * any more than a backtick opens a Lean span. A language with no
 * painter reads as `plain` until it has one. */
export type DocEditor = 'lean' | 'markdown' | 'plain'

/** How wide the right pane sits when both are on screen. `even` splits
 * the room; `narrow` and `side` are panes whose content has its own
 * width (a compiled page, a column of diagnostics) and would only
 * dilute the writing by taking half. */
export type DocPane = 'even' | 'narrow' | 'side'

/** What the render pane's bar offers — the thing you press to ask
 * "does this read?". The TeX engine compiles and answers with a log;
 * the painter answers with what it could not read. */
export type DocCheck = 'tex' | 'prose' | 'none'

/** ONE table for everything the two panes DO, per language.
 *
 * `.md` and `.tex` are two ROWS of this, not two branches of the shell
 * (owner, 2026-09-06: "the two must operate alike"). Before it the
 * shell decided the tab set, the editor, the pane width and whether
 * there was anything to check in four separate places, and the two
 * formats drifted apart in every one of them: markdown had no bar over
 * its render at all, and TeX had no painter under its caret.
 *
 * The one row where they legitimately differ is `scrollSync`, and the
 * reason is in the medium: a `.tex` render is a compiled pdf inside the
 * browser's own viewer, which takes no instruction from the page. Where
 * a pane is ours, the render follows the writing. */
export interface DocMode {
  panel: DocPanel
  editor: DocEditor
  /** the third tab's word, or null where there is no second pane and
   * so no choice to offer */
  third: 'render' | 'info' | null
  /** the render pane follows the source pane's scroll, proportionally */
  scrollSync: boolean
  check: DocCheck
  pane: DocPane
}

const PLAIN: DocMode = {
  panel: 'none',
  editor: 'plain',
  third: null,
  scrollSync: false,
  check: 'none',
  pane: 'even',
}

const MODES: Record<string, DocMode> = {
  '.md': {
    panel: 'render',
    editor: 'markdown',
    third: 'render',
    scrollSync: true,
    check: 'prose',
    pane: 'even',
  },
  '.tex': {
    panel: 'pdf-render',
    editor: 'plain',
    third: 'render',
    // the pane is the browser's pdf viewer inside an <object>; nothing
    // on this page can drive its scroll, and pretending to would be a
    // control that does nothing
    scrollSync: false,
    check: 'tex',
    pane: 'narrow',
  },
  '.lean': {
    panel: 'info',
    editor: 'lean',
    third: 'info',
    // the Info panel answers the CARET, not the scroll: it is already
    // following the reader, one goal at a time
    scrollSync: false,
    check: 'none',
    pane: 'side',
  },
  '.txt': PLAIN,
  '.pdf': { ...PLAIN, panel: 'viewer' },
  '.png': { ...PLAIN, panel: 'image' },
  '.jpg': { ...PLAIN, panel: 'image' },
  '.svg': { ...PLAIN, panel: 'image' },
}

function ext(path: string): string {
  const i = path.lastIndexOf('.')
  return i < 0 ? '' : path.slice(i).toLowerCase()
}

export function modeFor(path: string): DocMode {
  return MODES[ext(path)] ?? PLAIN
}

export function panelFor(path: string): DocPanel {
  return modeFor(path).panel
}

export function editorFor(path: string): DocEditor {
  return modeFor(path).editor
}

/** Where the render pane sits when the source pane is HERE.
 *
 * Proportional on each pane's own SCROLLABLE range, not on its height:
 * a rendered document is a different length from its source (a fence
 * paints shorter, a heading taller), so mapping raw pixels drifts a
 * page apart by the bottom. Ends therefore meet — top with top, bottom
 * with bottom — which is the only mapping a reader can check at a
 * glance. A source with nothing to scroll leaves the render where it
 * is: 0/0 is not a position.
 *
 * The `.tex` viewer has no mapping of its own to copy (its pane is a
 * pdf the browser owns), so this is the console's one answer for it. */
export function syncedScrollTop(
  source: { scrollTop: number; scrollHeight: number; clientHeight: number },
  target: { scrollHeight: number; clientHeight: number },
): number {
  const from = source.scrollHeight - source.clientHeight
  const to = target.scrollHeight - target.clientHeight
  if (from <= 0 || to <= 0) return 0
  const ratio = Math.min(1, Math.max(0, source.scrollTop / from))
  return Math.round(ratio * to)
}

// -- the split's divider -----------------------------------------------------

/*
 * Where the reader put the line between writing and reading.
 *
 * The two panes are not fixed halves: a `.tex` source is long lines and
 * a `.md` render is a column of prose, and which one wants the room is
 * the reader's answer, not the mode table's. So the divider moves — by
 * pointer and by key, one grammar — and the ratio is remembered for
 * whoever is looking, in their own browser.
 *
 * The law lives here rather than in the shell because it is the part
 * with a right answer, and because the shell is where it would drift
 * between `.md` and `.tex` (which is what happened to every other pane
 * decision before `modeFor` collected them).
 */

/** The smallest share a pane may be squeezed to. A pane dragged to
 * nothing is not a layout — it is the `source`/`render` tabs, which the
 * segmented control already offers, reached by accident. */
export const SPLIT_MIN = 0.2

/** Half and half: the mode table's `even` is still the starting truth,
 * and it is what a viewer with nothing stored gets. */
export const SPLIT_DEFAULT = 0.5

/** One key press. Small enough to place a line, large enough that
 * crossing the pane takes a held key rather than a career. */
export const SPLIT_NUDGE = 0.02

/** Per viewer, per browser — never per document. A person who wants a
 * wide editor wants it for the writing, not for one file. */
export const SPLIT_KEY = 'asterism.docSplit'

/** The ratio, inside the law. Anything unreadable falls back to half —
 * a stored string from an older build, a NaN out of a zero-width drag. */
export function clampSplit(ratio: number): number {
  if (!Number.isFinite(ratio)) return SPLIT_DEFAULT
  return Math.min(1 - SPLIT_MIN, Math.max(SPLIT_MIN, ratio))
}

/** Keys walk the same grammar as the pointer (DESIGN.md). Anything this
 * does not own returns null, so the handler leaves the event alone. */
export function splitStep(ratio: number, key: string): number | null {
  if (key === 'ArrowLeft') return clampSplit(ratio - SPLIT_NUDGE)
  if (key === 'ArrowRight') return clampSplit(ratio + SPLIT_NUDGE)
  if (key === 'Home') return SPLIT_MIN
  if (key === 'End') return 1 - SPLIT_MIN
  return null
}

/** What this viewer last chose. Every access is guarded: a private
 * window, cleared site data or a browser set to refuse storage all
 * throw on the ACCESSOR, and a page that let that through would fail to
 * lay out for the reason "we could not remember". */
export function readSplit(): number {
  try {
    const v = localStorage.getItem(SPLIT_KEY)
    return v === null ? SPLIT_DEFAULT : clampSplit(Number(v))
  } catch {
    return SPLIT_DEFAULT
  }
}

export function writeSplit(ratio: number): void {
  try {
    localStorage.setItem(SPLIT_KEY, String(clampSplit(ratio)))
  } catch {
    /* the layout is the point; remembering it is the courtesy */
  }
}

/** The kinds the console can put in a box. A pdf and an image are
 * shown, not written. */
export function isTextDoc(path: string): boolean {
  return ['.md', '.tex', '.txt', '.lean'].includes(ext(path))
}

/** This door writes `user/` and nothing else (§1.2-1: the areas'
 * separation is the point, and the engine refuses the rest anyway). */
export function editable(ref: DocRef): boolean {
  return ref.kind === 'doc' && ref.path.startsWith('user/') && isTextDoc(ref.path)
}

/** `source` = the left pane alone, `render` = the right pane alone,
 * `split` = both. The segmented control names the third one `render`
 * for prose and `info` for Lean. */
export type DocView = 'source' | 'split' | 'render'

/** What a document opens on.
 *
 * A document with NO companion panel opens as source whether or not it
 * is editable: `split` would draw a pane with nothing in it, and the
 * view control is absent for those kinds anyway. Everything the person
 * can write opens split (writing beside its reading); read-only prose
 * opens on its render, and read-only Lean still opens split because the
 * caret is what drives the Info panel. */
export function defaultView(ref: DocRef): DocView {
  const panel = panelFor(ref.path)
  if (panel === 'none') return 'source'
  if (editable(ref)) return 'split'
  if (panel === 'info') return 'split'
  return 'render'
}

/** Whose writing this is — shown only when it is not the reader's.
 *
 * `user/` returns null: the settled norm earns no ink (DESIGN.md). The
 * `agent/` area holds two hands — what the theory layer landed for its
 * reviewer (theory_wake_design.md §4), and what the Assistant left
 * there before its write moved to `user/` (owner, 2026-09-06) — and
 * the listing's own record is what tells them apart. */
export function ownerOf(ref: DocRef, theory?: TheoryMeta | null): string | null {
  if (ref.kind === 'task') return "the engine's — read-only"
  if (ref.path.startsWith('user/') || ref.path === 'user') return null
  return theory ? "the theory layer's — read-only" : "the Assistant's — read-only"
}

/** One paper, as `/api/projects/{p}/papers` lists it. */
export interface PaperRow {
  id: string
  title: string | null
  source_name: string
  path: string
  area: string
}

export interface RailInput {
  /** `/api/projects/{p}/docs` — flat and root-relative */
  entries: DocEntry[]
  /** `/api/projects/{p}/papers` — both areas */
  papers: PaperRow[]
  /** the task whose writing is listed; null = the shelf has none */
  task: string | null
  /** that task's detail, once it has answered */
  taskFiles: { problem_files: string[]; proof_files: string[]; hasReport: boolean } | null
  /** the rail's name filter; '' = none */
  query: string
}

export interface RailRow {
  ref: DocRef
  name: string
  depth: number
  kind: 'file' | 'dir'
  theory?: TheoryMeta | null
  /** never set here: whether a document holds unsaved writing is the
   * draft store's answer (`lib/docDrafts`), read by the row that draws
   * it. Declared so nobody adds a second source for it. */
  dirty?: never
}

export type RailGroupId = 'yours' | 'papers' | 'agent' | 'engine' | 'proofs'

export interface RailGroup {
  id: RailGroupId
  label: string
  /** how many rows the group is showing — the header draws
   * `label · count`, which is where `proofs · 186` comes from */
  count: number
  rows: RailRow[]
  /** secondary groups fold away by default; `yours` never does */
  secondary: boolean
}

/* The five groups, and the ONE order the rail reads them in. This
 * comment is the reviewed law (docs_tab_spec.md §B4):
 *
 * 1. yours   — every `user/` entry except `user/papers/**`, in the
 *              API's own tree order, depth from the path. The area
 *              folder itself is not a row (it is the heading). Primary,
 *              and it renders even when empty: it is where a first file
 *              starts.
 * 2. papers  — one row per paper in BOTH areas, named `title ??
 *              source_name` and sorted by that name; the paper's own
 *              files nest one deeper. `meta.json` and the map spawn's
 *              `.index_attempt/` sandbox never appear.
 * 3. agent   — `agentRows` (theory documents first, newest first) minus
 *              `agent/papers/**`.
 * 4. engine  — the chosen task's top-level files, in the order a person
 *              opens them: REPORT, PROGRAMME, BRIEF, TREE, Root, Defs,
 *              then anything else alphabetically — each only if the
 *              task actually wrote it. REPORT.md additionally waits on
 *              `ingest_report`, the DB's SoT. Absent with no task.
 * 5. proofs  — the task's proof files, the `L_` brick prefix dropped
 *              from the NAME while the ref keeps the whole path.
 *
 * A query keeps only rows whose name carries it, case-insensitively,
 * and a group left with nothing is dropped — `yours` included, because
 * with a filter running an empty group is an answer, not an invitation.
 */

/** The engine's files, in the order a person opens them. */
const ENGINE_ORDER = [
  'REPORT.md',
  'PROGRAMME.md',
  'BRIEF.md',
  'TREE.md',
  'Root.lean',
  'Defs.lean',
]

/** A paper's own files, in reading order: the document, its text, then
 * the map into it. */
function paperFileRank(name: string): number {
  if (name.startsWith('paper.')) return 0
  if (name === 'text.md') return 1
  if (name === 'map.md') return 2
  return 3
}

const lastSegment = (path: string): string => path.split('/').pop() ?? path

/** Depth inside an area: `user/a.md` is 0, `user/n/a.md` is 1. */
const areaDepth = (path: string): number => path.split('/').length - 2

const inPapers = (path: string): boolean =>
  /^(user|agent)\/papers(\/|$)/.test(path)

export function railGroups(input: RailInput): RailGroup[] {
  const { entries, papers, task, taskFiles, query } = input
  const out: RailGroup[] = []

  const yours: RailRow[] = entries
    .filter((e) => e.path.startsWith('user/') && !inPapers(e.path))
    .map((e) => ({
      ref: { kind: 'doc', path: e.path } as DocRef,
      name: lastSegment(e.path),
      depth: areaDepth(e.path),
      kind: e.kind,
      theory: e.theory ?? null,
    }))
  out.push({ id: 'yours', label: 'yours', count: yours.length, rows: yours, secondary: false })

  const paperRows: RailRow[] = []
  for (const p of [...papers].sort((a, b) =>
    (a.title ?? a.source_name).localeCompare(b.title ?? b.source_name),
  )) {
    paperRows.push({
      ref: { kind: 'doc', path: p.path },
      name: p.title ?? p.source_name,
      depth: 0,
      kind: 'dir',
      theory: null,
    })
    // every direct child the listing shows, minus the two that are not
    // the paper: its identity record, and the sandbox the map spawn ran
    // in. Found by prefix rather than by the three known names — the
    // document itself is `paper.<whatever was uploaded>`.
    const children = entries.filter(
      (e) =>
        e.kind === 'file' &&
        e.path.startsWith(`${p.path}/`) &&
        e.path.slice(p.path.length + 1).indexOf('/') < 0 &&
        lastSegment(e.path) !== 'meta.json',
    )
    children.sort(
      (a, b) =>
        paperFileRank(lastSegment(a.path)) - paperFileRank(lastSegment(b.path)) ||
        a.path.localeCompare(b.path),
    )
    for (const c of children)
      paperRows.push({
        ref: { kind: 'doc', path: c.path },
        name: lastSegment(c.path),
        depth: 1,
        kind: 'file',
        theory: null,
      })
  }
  out.push({
    id: 'papers',
    label: 'papers',
    count: paperRows.length,
    rows: paperRows,
    secondary: true,
  })

  const agent: RailRow[] = agentRows(entries)
    .filter((e) => !inPapers(e.path))
    .map((e) => ({
      ref: { kind: 'doc', path: e.path } as DocRef,
      name: lastSegment(e.path),
      depth: areaDepth(e.path),
      kind: e.kind,
      theory: e.theory ?? null,
    }))
  out.push({ id: 'agent', label: 'agent', count: agent.length, rows: agent, secondary: true })

  if (task !== null) {
    const present = new Set(taskFiles?.problem_files ?? [])
    const rest = [...present].filter((n) => !ENGINE_ORDER.includes(n)).sort()
    const engine: RailRow[] = [...ENGINE_ORDER, ...rest]
      .filter((n) => present.has(n))
      .filter((n) => n !== 'REPORT.md' || (taskFiles?.hasReport ?? false))
      .map((n) => ({
        ref: { kind: 'task', task, path: n } as DocRef,
        name: n,
        depth: 0,
        kind: 'file' as const,
        theory: null,
      }))
    out.push({
      id: 'engine',
      label: 'engine',
      count: engine.length,
      rows: engine,
      secondary: true,
    })

    const proofs: RailRow[] = (taskFiles?.proof_files ?? []).map((n) => ({
      ref: { kind: 'task', task, path: `proofs/${n}` } as DocRef,
      name: n.replace(/^L_/, ''),
      depth: 0,
      kind: 'file' as const,
      theory: null,
    }))
    out.push({
      id: 'proofs',
      label: 'proofs',
      count: proofs.length,
      rows: proofs,
      secondary: true,
    })
  }

  const q = query.trim().toLowerCase()
  if (q === '') return out
  return out
    .map((g) => {
      const rows = g.rows.filter((r) => r.name.toLowerCase().includes(q))
      return { ...g, rows, count: rows.length }
    })
    .filter((g) => g.rows.length > 0)
}

/** Where a new file or folder starts (§D4).
 *
 * The folder you are standing in: the open folder itself, or the open
 * file's parent. Anything else — nothing open, the Assistant's area,
 * the engine's writing — starts at the area root, because this door
 * writes `user/` and a selection in another group must not redirect a
 * create into it. A paper's folder is excluded for the same reason the
 * `yours` group leaves it out: the shelf maintains it. */
export function createFolder(ref: DocRef | null, isDir: boolean): string {
  if (ref === null || ref.kind !== 'doc') return 'user'
  if (!ref.path.startsWith('user/') || inPapers(ref.path)) return 'user'
  return isDir ? ref.path : ref.path.split('/').slice(0, -1).join('/')
}

/** Where a `user/` thing may be moved to (§D8).
 *
 * The area itself first, then its folders in tree order. Absent: the
 * folder the thing is already in (a move to where it is is not a move),
 * and — for a folder — itself and everything under it. The papers area
 * is absent too, for the same reason the `yours` group leaves it out: a
 * paper is a folder of four files the shelf maintains, not a place a
 * person files their notes. */
export function moveTargets(
  entries: DocEntry[],
  path: string,
  kind: 'file' | 'dir',
): string[] {
  const parent = path.split('/').slice(0, -1).join('/')
  const all = [
    'user',
    ...entries
      .filter((e) => e.kind === 'dir' && e.path.startsWith('user/') && !inPapers(e.path))
      .map((e) => e.path),
  ]
  return all.filter((f) => {
    if (f === parent) return false
    if (kind === 'dir' && (f === path || f.startsWith(`${path}/`))) return false
    return true
  })
}

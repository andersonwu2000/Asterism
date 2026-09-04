import { useEffect, useMemo, useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import { Link, navigate } from '../lib/router'
import { projectPath } from '../lib/projectRoute'
import { ConfirmWindow } from '../components/ConfirmWindow'
import { Button } from '../components/ui'
import ListField from '../components/ListField'
import { DiagList, LeanBlock, countErrors } from '../components/LeanBlock'
import { boxDiags, engineWord, useLeanSession, type LeanCursor } from '../lib/leanSession'
import { claimLeanSlot, releaseLeanSlot, useLeanSlotActive } from '../lib/leanSlot'
import type { PaperShelfItem } from '../lib/types'
import { frameClass } from '../lib/textFrame'

/*
 * Problem authoring, mathematician-first: a name, a natural-language
 * description, and sensible defaults. The frontmatter is controls, not
 * yaml; pinned Lean files stay behind an "advanced" fold. Everything
 * here can be changed later on the task's own page.
 */

const NAME_RE = /^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*$/

/** kernel-blessed default — sending it explicitly is idempotent */
const DEFAULT_AXIOMS = ['propext', 'Quot.sound', 'Classical.choice']

/** The two files an author may pin. Declared, not written twice: they
 * differ in caption and seed text and in nothing else. */
const LEAN_BOXES = [
  {
    id: 'defs' as const,
    caption: 'Defs.lean — your own definitions; the engine must use these, never re-derive them.',
    placeholder: (n: string) =>
      `import Mathlib\n\nnamespace Problems.${n}\n\n-- your definitions\n\nend Problems.${n}`,
  },
  {
    id: 'root' as const,
    caption:
      'Root.lean — pins the exact statement that must be proved before the task can finish (theorem main : <stmt> := by sorry).',
    placeholder: (n: string) =>
      `import Mathlib\nimport Problems.${n}.Defs\n\nnamespace Problems.${n}\n\ntheorem main : <statement> := by sorry\n\nend Problems.${n}`,
  },
]

export default function New({ project }: { project?: string | null }) {
  // Which shelf the task is filed under. §3.1: the name's first segment
  // is only the DEFAULT — arriving from a Project's own "New task"
  // means that shelf, whatever the name turns out to say, and serve
  // takes `project` for exactly this (`d29983f3`).
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  // the standing word (v40): what holds however the goal is later
  // rewritten. The engine reads it at every depth and can never amend
  // it, which is exactly why it is asked for separately.
  const [word, setWord] = useState('')
  const [showLean, setShowLean] = useState(false)
  const [defs, setDefs] = useState('')
  const [root, setRoot] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [shelf, setShelf] = useState<PaperShelfItem[]>([])
  const [papers, setPapers] = useState<Set<string>>(new Set())
  const [showConstraints, setShowConstraints] = useState(false)
  // the shelf is a LIBRARY, not a checklist (owner, 2026-08-27): it
  // was rendering one checkbox per paper, so an ordinary shelf buried
  // the rest of the form under forty rows of filename. Collapsed, this
  // field costs one line; the list opens under the cursor and closes
  // when you leave it — in flow, never floating (DESIGN.md: prefer
  // dimming over popups, modals only for irreversible destruction).
  const [paperQ, setPaperQ] = useState('')
  const [paperOpen, setPaperOpen] = useState(false)
  const [axioms, setAxioms] = useState<string[]>(DEFAULT_AXIOMS)
  const [forbidden, setForbidden] = useState<string[]>([])

  // Which shelf's papers are on offer: the one the task will be filed
  // on. Arriving from a Project names it; typing a name picks the same
  // default registration would (§3.1), and a paper is one of its
  // Project's documents now (§3.9) — offering the workspace's would
  // offer papers this task's engine cannot read.
  const shelfProject = project ?? (name.includes('.') ? name.split('.')[0] : name)
  // one silent fetch; failure (no such Project yet, older engine) just
  // leaves the block empty
  useEffect(() => {
    if (shelfProject.trim() === '') {
      setShelf([])
      return
    }
    let cancelled = false
    apiGet<{ papers: PaperShelfItem[] }>(
      `/api/projects/${encodeURIComponent(shelfProject)}/papers`,
    )
      .then((d) => !cancelled && setShelf(d.papers))
      .catch(() => !cancelled && setShelf([]))
    return () => {
      cancelled = true
    }
  }, [shelfProject])

  // a paper reads by its TITLE where it has one —
  // `div-class-title-a-proof-of-the-erd-s-...pdf` is a filename, not a
  // name (the picker was showing only that)
  const paperName = (p: PaperShelfItem) => p.title ?? p.source_name
  const chosen = useMemo(
    () => shelf.filter((p) => papers.has(p.id)),
    [shelf, papers],
  )
  // In the window a bound paper KEEPS its place, marked — the whole
  // point of opening the shelf is seeing it, and unbinding belongs
  // where binding happened. (The chips on the form are the settled
  // summary for when the window is shut, not a second copy of this.)
  const offered = useMemo(() => {
    const q = paperQ.trim().toLowerCase()
    if (q === '') return shelf
    return shelf.filter(
      (p) =>
        paperName(p).toLowerCase().includes(q) ||
        p.source_name.toLowerCase().includes(q),
    )
  }, [shelf, paperQ])

  const togglePaper = (id: string) =>
    setPapers((old) => {
      const next = new Set(old)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  // the authoring InfoView: one interactive engine session (reserved
  // slot). Pause typing → elaborate + diagnostics; move the caret →
  // the goal at that position (live inside `by` blocks).
  const [cursor, setCursor] = useState<LeanCursor | null>(null)
  // the reader's Lean runs on ONE reserved slot; the authoring check
  // holds it only while an editor here is focused (claimed on focus).
  const slotId = 'new-authoring'
  const leanActive = useLeanSlotActive(slotId)
  useEffect(() => () => releaseLeanSlot(slotId), [])
  const check = useLeanSession({
    enabled: showLean && (defs.trim() !== '' || root.trim() !== ''),
    active: leanActive,
    parts: [
      { id: 'defs', code: defs },
      { id: 'root', code: root },
    ],
    cursor,
  })
  const nErr = countErrors([
    ...check.preamble,
    ...(check.parts.defs ?? []),
    ...(check.parts.root ?? []),
  ])
  // The VERDICT only. The engine's PHASE is a separate fact and each
  // box says it in its own InfoView — `checking…` used to appear in
  // both places at once, which is one fact drawn twice.
  const checkWord =
    check.phase === 'ready' && !check.detail
      ? nErr === 0
        ? '✓ elaborates'
        : `${nErr} error${nErr === 1 ? '' : 's'}`
      : ''
  const engineSays = engineWord(check)

  // What ONE box has to say — its own diagnostics, and (only while the
  // caret is in it) the goal there. NOT the preamble: a `#check` result
  // reaches us with `line: null` (measured — serve's `_map_diags` can
  // only bin an unpositioned diagnostic as `_preamble`), so folding
  // that bin into Defs printed the ROOT box's output above the Defs
  // box (owner screenshot, 2026-08-27). Un-attributable output belongs
  // to the pair, and is rendered as the pair's own row.
  const partInfo = (part: 'defs' | 'root') => {
    const mine = cursor?.part === part
    const g = check.goal
    const goal =
      mine && !engineSays && g && g !== 'no goals' && !g.startsWith('<no goals')
        ? g.replace(/^```lean\n?/, '').replace(/\n?```\s*$/, '')
        : null
    const status = !mine
      ? ''
      : engineSays
        ? engineSays
        : goal
          ? (check.note ?? '')
          : g
            ? 'no goals here — the caret is outside an open `by` proof'
            : ''
    return {
      diags: boxDiags(check, part),
      goal,
      status,
    }
  }

  const nameOk = NAME_RE.test(name)
  // concrete reason, live as the user types (or after a blur): silent
  // disabled buttons make people re-read the form instead of the fix
  const nameError =
    name !== '' && !nameOk
      ? /\s/.test(name)
        ? "spaces aren't allowed — use underscores"
        : 'names are dot-separated identifiers — try Topology.my_theorem'
      : null
  const hasLean = defs.trim() !== '' || root.trim() !== ''

  const create = async () => {
    setBusy(true)
    setError(null)
    // The description IS the charter, verbatim — no `# name` title, no
    // `## Statement` heading. Named sections stopped being parsed
    // (`23146735`) and the whole thing reaches the agent as written; a
    // form that keeps stamping dead scaffolding is exactly what that
    // commit indicted (531 of 611 Manifests still carried a
    // `## Lemma hints` retired in 2026-07, because an importer kept
    // writing it). This form would have been the next such importer.
    try {
      await apiPost<{ problem: string }>('/api/problems/create', {
        name,
        ...(project ? { project } : {}),
        charter: desc.trim(),
        ...(word.trim() === '' ? {} : { word: word.trim() }),
        settings: {
          // whether finished work enters the Library is decided by a
          // human AT SIGN-OFF (owner: no automatic harvest) — true
          // here just raises that review gate when the problem ends
          library: true,
          axioms_whitelist: axioms,
          forbidden_lemmas: forbidden,
        },
        defs: defs.trim() === '' ? null : defs,
        root: root.trim() === '' ? null : root,
        ...(papers.size > 0 ? { papers: [...papers] } : {}),
      })
      // Land on the new task where it now LIVES. `/problems/<name>` is
      // the legacy address and only redirects — through the Sky, which
      // is not what someone who just wrote a description is asking to
      // see. When the shelf is known, address the task directly.
      navigate(
        project
          ? projectPath(project, 'tasks', name)
          : `/problems/${encodeURIComponent(name)}`,
      )
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-6">
      <div className="mb-1 flex items-baseline gap-3">
        <Link
          to={project ? projectPath(project, 'tasks') : '/'}
          className="text-[11px] text-ink-faint transition-colors hover:text-ink"
        >
          ‹ {project ?? 'projects'}
        </Link>
        <h1 className="font-display text-[22px] font-medium text-ink">New task</h1>
      </div>
      <p className="mb-5 max-w-[70ch] text-xs text-ink-faint">
        Say what you want proved, in your own words. The engine plans, defines, and proves
        from this description; you review its statements before anything is kept.
      </p>

      <label className="mb-1 block text-[11px] font-medium tracking-widest text-ink-faint uppercase">
        name
      </label>
      <input
        className="mb-1 w-96 rounded-lg border border-edge bg-surface px-2.5 py-1.5 font-mono text-sm text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
        placeholder="Topology.my_theorem"
        value={name}
        onChange={(e) => setName(e.target.value)}
        spellCheck={false}
        autoFocus
      />
      <div className="mb-4 min-h-4 text-[11px] text-danger">{nameError ?? ' '}</div>

      <label className="mb-1 block text-[11px] font-medium tracking-widest text-ink-faint uppercase">
        what should be proved?
      </label>
      <textarea
        className="h-64 w-full resize-y rounded-lg border border-edge bg-surface p-3 text-[13px] leading-relaxed text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
        placeholder={
          'Describe the mathematics in natural language: the objects involved, the ' +
          'statements you want, any routes to prefer or avoid.\n\nExample: Compute the ' +
          'singular homology of the n-sphere with coefficients in an arbitrary ring R. ' +
          'The Mayer–Vietoris machinery is already in the Library — cite it, do not rebuild it.'
        }
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
      />

      <label
        className="mt-4 mb-1 block text-[11px] font-medium tracking-widest text-ink-faint uppercase"
        title="carried verbatim into every agent at every depth of the discussion tree. The engine reads it and has no way to amend it, while the goal above it may be amended by request."
      >
        anything that must hold whatever happens <span className="lowercase">(optional)</span>
      </label>
      <textarea
        className="h-24 w-full resize-y rounded-lg border border-edge bg-surface p-3 text-[13px] leading-relaxed text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
        placeholder={
          'Standing instructions the engine may never rewrite: routes to prefer or avoid, ' +
          'standards to keep, what counts as done.'
        }
        value={word}
        onChange={(e) => setWord(e.target.value)}
      />

      {shelf.length > 0 && (
        <div className="mt-4">
          <label className="mb-1 block text-[11px] font-medium tracking-widest text-ink-faint uppercase">
            ground it in papers <span className="lowercase">(optional)</span>
          </label>
          <p className="mb-2 text-[11px] text-ink-faint">
            the engine reads these for definitions and proof routes (you can bind more
            later)
          </p>
          {/* the settled summary for when the window is shut: what is
              bound, and a click to drop it without reopening */}
          {chosen.length > 0 && (
            <div className="mb-2 flex max-w-2xl flex-wrap gap-1.5">
              {chosen.map((p) => (
                <button
                  key={p.id}
                  data-paper-chip
                  className="group/chip flex max-w-full cursor-pointer items-center gap-1.5 rounded-lg border border-edge bg-surface px-2.5 py-1 transition-colors hover:border-edge-strong"
                  title={`${p.source_name} — click to drop it`}
                  onClick={() => togglePaper(p.id)}
                >
                  <span
                    className={
                      'truncate text-[12px] text-ink ' + (p.title ? '' : 'font-mono')
                    }
                  >
                    {paperName(p)}
                  </span>
                  <span className="shrink-0 text-[11px] text-ink-faint transition-colors group-hover/chip:text-ink">
                    ×
                  </span>
                </button>
              ))}
            </div>
          )}
          <button
            data-paper-open
            className="cursor-pointer rounded-lg border border-edge bg-surface px-3 py-1.5 text-xs text-ink-dim transition-colors hover:border-edge-strong hover:text-ink"
            onClick={() => {
              setPaperQ('')
              setPaperOpen(true)
            }}
          >
            {chosen.length > 0
              ? `choose from the shelf — ${chosen.length} of ${shelf.length} bound`
              : `choose from the shelf — ${shelf.length} paper${shelf.length === 1 ? '' : 's'}`}
          </button>
        </div>
      )}

      <p className="mt-4 text-[11px] text-ink-faint">
        When the engine finishes, the results wait for your sign-off — whether they enter the
        Library is decided there, not here.
      </p>

      <button
        className="mt-4 mb-2 block text-xs text-ink-dim transition-colors hover:text-ink"
        onClick={() => setShowLean((v) => !v)}
      >
        {showLean ? '▾' : '▸'} advanced — pin exact Lean (Defs.lean / Root.lean)
      </button>
      {showLean && (
        <div className="mb-3 flex flex-col gap-3">
          {/* The pair's own row: the verdict that gates Create, and any
              output the engine could not pin to a box — a `#check`
              result arrives unpositioned, so it belongs to the file,
              not to whichever box happens to be first. The per-box
              word lives in each box's InfoView, as it does in a probe. */}
          {(() => {
            // the engine's word belongs wherever the reader is: in the
            // box holding the caret, or here while no box holds it
            const word = cursor === null ? engineSays : ''
            const line = word !== '' ? word : checkWord
            if (line === '' && check.preamble.length === 0) return null
            return (
              <div className="rounded-xl border border-edge px-3 py-2">
                {line !== '' && <div className="text-[11px] text-ink-faint">{line}</div>}
                <DiagList diags={check.preamble} />
              </div>
            )
          })()}
          {LEAN_BOXES.map((box) => {
            const info = partInfo(box.id)
            return (
              <LeanBlock
                key={box.id}
                caption={box.caption}
                value={box.id === 'defs' ? defs : root}
                onChange={box.id === 'defs' ? setDefs : setRoot}
                onCaret={(pos) => setCursor({ part: box.id, ...pos })}
                onFocus={() => claimLeanSlot(slotId)}
                placeholder={box.placeholder(name || '<name>')}
                heightClass="min-h-40 h-auto max-h-[28rem] field-sizing-content"
                status={info.status}
                goal={info.goal}
                diags={info.diags}
              />
            )
          })}
        </div>
      )}

      <button
        className="mb-2 block text-xs text-ink-dim transition-colors hover:text-ink"
        onClick={() => setShowConstraints((v) => !v)}
      >
        {showConstraints ? '▾' : '▸'} advanced — engine constraints
      </button>
      {showConstraints && (
        <div className="mb-3 flex flex-col gap-4">
          <ListField
            label="forbidden lemmas"
            hint="add pattern (e.g. sperner*)"
            values={forbidden}
            onChange={setForbidden}
          />
          <ListField
            label="axiom whitelist"
            hint="add axiom"
            values={axioms}
            onChange={setAxioms}
          />
        </div>
      )}

      {error && (
        <pre className={frameClass({ tone: 'ink', className: 'mb-3' })}>
          {error}
        </pre>
      )}

      <div className="mt-2 flex items-center gap-3">
        {/* disabled buttons swallow pointer events — the "why" tooltip
            must live on a wrapper to actually show */}
        <span title={desc.trim() === '' ? 'write a description first' : undefined}>
          <Button
            variant="primary"
            disabled={busy || !nameOk || desc.trim() === ''}
            onClick={() => void create()}
          >
            {busy ? (hasLean ? 'Type-checking Lean files…' : 'Creating…') : 'Create task'}
          </Button>
        </span>
        {busy && hasLean && (
          <span className="text-[11px] text-ink-faint">
            lake build runs first — this can take minutes
          </span>
        )}
        {!busy && (
          <Button variant="ghost" onClick={() => navigate('/')}>
            Cancel
          </Button>
        )}
      </div>

      {/* The shelf, floating (owner, 2026-08-27). Browsing a
          collection to choose from it is a task of its own: inlined it
          buried the form, and a bounded inline list made the reader
          choose through a slot. It wears the one floating shape like
          every other window; the search box is where the focus lands,
          so the window does not take it. Nothing here is irreversible,
          so there is nothing to confirm: picks apply as they are made
          and the window just closes. */}
      {paperOpen && (
        <ConfirmWindow
          title="Ground it in papers"
          autoFocus={false}
          onClose={() => setPaperOpen(false)}
        >
          <p className="mt-1 text-xs text-ink-dim">
            the engine reads these for definitions and proof routes
          </p>
          <input
            className="mt-3 w-full rounded-md border border-edge bg-bg px-2.5 py-1.5 text-[13px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
            placeholder={`search ${shelf.length} papers by title or filename`}
            value={paperQ}
            onChange={(e) => setPaperQ(e.target.value)}
            spellCheck={false}
            autoFocus
          />
          <div className="mt-2 max-h-[52vh] overflow-y-auto rounded-lg border border-edge">
            {offered.length === 0 ? (
              <div className="px-3 py-3 text-[11px] text-ink-faint">
                nothing on the shelf matches
              </div>
            ) : (
              offered.map((p) => {
                const bound = papers.has(p.id)
                return (
                  <button
                    key={p.id}
                    data-paper-option
                    data-bound={bound ? '' : undefined}
                    className="flex w-full cursor-pointer items-baseline gap-2.5 px-3 py-1.5 text-left transition-colors hover:bg-wash"
                    onClick={() => togglePaper(p.id)}
                  >
                    {/* bound reads as brightness, as everywhere else:
                        the mark is the same glyph in both states so
                        the rows do not shift when one is taken */}
                    <span
                      className={
                        'shrink-0 text-[11px] ' + (bound ? 'text-ink' : 'text-ink-faint/25')
                      }
                    >
                      ✓
                    </span>
                    <span className="min-w-0 flex-1">
                      <span
                        data-paper-name
                        className={
                          'block truncate text-[12.5px] ' +
                          (bound ? 'text-ink' : 'text-ink-dim') +
                          (p.title ? '' : ' font-mono')
                        }
                      >
                        {paperName(p)}
                      </span>
                      <span className="block truncate font-mono text-[10.5px] text-ink-faint">
                        {/* the filename earns a line only when it is
                            NOT already the name above it */}
                        {p.title ? `${p.source_name} · ` : ''}
                        {p.pages} pp
                      </span>
                    </span>
                  </button>
                )
              })
            )}
          </div>
          <div className="mt-3 flex items-center justify-between">
            <span className="text-[11px] text-ink-faint">
              {chosen.length === 0
                ? 'none bound — the engine will work from your description alone'
                : `${chosen.length} bound`}
            </span>
            <Button variant="outline" onClick={() => setPaperOpen(false)}>
              Done
            </Button>
          </div>
        </ConfirmWindow>
      )}
    </div>
  )
}

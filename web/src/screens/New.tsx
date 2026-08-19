import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import { navigate } from '../lib/router'
import { Button } from '../components/ui'
import ListField from '../components/ListField'
import { DiagList, countErrors } from '../components/LeanProbe'
import { useLeanSession, type LeanCursor } from '../lib/leanSession'
import { claimLeanSlot, releaseLeanSlot, useLeanSlotActive } from '../lib/leanSlot'
import { LeanEditor } from '../components/LeanEditor'
import type { PaperShelfItem } from '../lib/types'

/*
 * Problem authoring, mathematician-first: a name, a natural-language
 * description, and sensible defaults. The frontmatter is controls, not
 * yaml; pinned Lean files stay behind an "advanced" fold. Everything
 * here can be changed later on the problem's Intent tab.
 */

const NAME_RE = /^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*$/

/** kernel-blessed default — sending it explicitly is idempotent */
const DEFAULT_AXIOMS = ['propext', 'Quot.sound', 'Classical.choice']

export default function New() {
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
  const [axioms, setAxioms] = useState<string[]>(DEFAULT_AXIOMS)
  const [forbidden, setForbidden] = useState<string[]>([])

  // the papers block only renders when a shelf exists — one silent
  // fetch; failure (older engine, empty workspace) hides it
  useEffect(() => {
    let cancelled = false
    apiGet<{ papers: PaperShelfItem[] }>('/api/papers')
      .then((d) => !cancelled && setShelf(d.papers))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

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
  // buffer verdict only — engine lifecycle states live in the goal
  // panel, where the eye already is
  const checkWord =
    check.phase === 'checking'
      ? 'checking…'
      : check.phase === 'ready' && !check.detail
        ? nErr === 0
          ? '✓ elaborates'
          : `${nErr} error${nErr === 1 ? '' : 's'}`
        : ''
  const engineWord =
    check.phase === 'dormant'
      ? 'click into a box below to check — the Lean engine follows your cursor'
      : check.phase === 'warming'
        ? 'engine warming — the check resumes on its own (a cold start can take a minute)'
        : check.phase === 'busy'
          ? 'the engine editor slot is busy elsewhere — retrying'
          : check.phase === 'connecting'
            ? 'connecting to the engine…'
            : check.detail
              ? `engine error: ${check.detail}`
              : null

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
      navigate(`/problems/${encodeURIComponent(name)}`)
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-6">
      <h1 className="font-display mb-1 text-[22px] font-medium text-ink">New problem</h1>
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
            ground it in papers
          </label>
          <p className="mb-2 text-[11px] text-ink-faint">
            the engine reads checked papers for definitions and proof routes (you can bind
            more later)
          </p>
          <div className="flex flex-col gap-1">
            {shelf.map((p) => (
              <label key={p.id} className="flex items-center gap-2 text-xs text-ink-dim">
                <input
                  type="checkbox"
                  checked={papers.has(p.id)}
                  onChange={() => togglePaper(p.id)}
                />
                <span className="font-mono text-[12px] text-ink">{p.source_name}</span>
              </label>
            ))}
          </div>
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
          <div className="min-h-4 text-[11px] text-ink-faint">{checkWord}</div>
          {check.preamble.length > 0 && <DiagList diags={check.preamble} />}
          <div>
            <div className="mb-1 text-[11px] text-ink-faint">
              Defs.lean — your own definitions; the engine must use these, never re-derive them.
            </div>
            <LeanEditor
              value={defs}
              onChange={setDefs}
              onCaret={(pos) => setCursor({ part: 'defs', ...pos })}
              onFocus={() => claimLeanSlot(slotId)}
              placeholder={`import Mathlib\n\nnamespace Problems.${name || '<name>'}\n\n-- your definitions\n\nend Problems.${name || '<name>'}`}
            />
            <DiagList diags={check.parts.defs ?? []} />
          </div>
          <div>
            <div className="mb-1 text-[11px] text-ink-faint">
              Root.lean — pins the exact statement that must be proved before the problem can
              finish (shape: <span className="font-mono">theorem main : &lt;stmt&gt; := by sorry</span>).
            </div>
            <LeanEditor
              value={root}
              onChange={setRoot}
              onCaret={(pos) => setCursor({ part: 'root', ...pos })}
              onFocus={() => claimLeanSlot(slotId)}
              placeholder={`import Mathlib\nimport Problems.${name || '<name>'}.Defs\n\nnamespace Problems.${name || '<name>'}\n\ntheorem main : <statement> := by sorry\n\nend Problems.${name || '<name>'}`}
            />
            <DiagList diags={check.parts.root ?? []} />
          </div>
          {check.phase !== 'idle' && (
            <div className="rounded-lg border border-edge bg-wash">
              <div className="flex items-baseline gap-2 border-b border-edge px-3 py-1.5">
                <span className="text-[10px] tracking-widest text-ink-faint uppercase">
                  goal at cursor
                </span>
                {cursor && (
                  <span className="font-mono text-[10px] text-ink-faint">
                    {cursor.part} L{cursor.line}
                  </span>
                )}
              </div>
              <pre className="max-h-56 overflow-auto px-3 py-2 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-ink">
                {engineWord ? (
                  <span className="text-ink-dim">{engineWord}</span>
                ) : !cursor ? (
                  <span className="text-ink-faint">
                    — place the cursor inside a `by` proof to see its goal
                  </span>
                ) : check.goal && check.goal !== 'no goals' && !check.goal.startsWith('<no goals') ? (
                  check.goal.replace(/^```lean\n?/, '').replace(/\n?```\s*$/, '')
                ) : (
                  <span className="text-ink-faint">
                    {check.goal
                      ? 'no goals — outside an open proof, or the proof is complete here'
                      : '— place the cursor inside a `by` proof to see its goal'}
                  </span>
                )}
              </pre>
              {check.note && !engineWord && (
                <div className="border-t border-edge px-3 py-1.5 text-[10px] text-ink-faint">
                  {check.note}
                </div>
              )}
            </div>
          )}
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
        <pre className="mb-3 rounded-lg border border-edge-strong bg-surface px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink">
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
            {busy ? (hasLean ? 'Type-checking Lean files…' : 'Creating…') : 'Create problem'}
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
    </div>
  )
}

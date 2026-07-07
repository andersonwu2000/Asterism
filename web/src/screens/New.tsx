import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import { navigate } from '../lib/router'
import { Button } from '../components/ui'
import ListField from '../components/ListField'
import { DiagList, countErrors, evalLean, type EvalDiag } from '../components/LeanProbe'
import type { PaperShelfItem } from '../lib/types'

/*
 * Problem authoring, mathematician-first: a name, a natural-language
 * description, and sensible defaults. The frontmatter is controls, not
 * yaml; pinned Lean files stay behind an "advanced" fold. Everything
 * here can be changed later on the problem's Manifest tab.
 */

const NAME_RE = /^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*$/

/** kernel-blessed default — sending it explicitly is idempotent */
const DEFAULT_AXIOMS = ['propext', 'Quot.sound', 'Classical.choice']

export default function New() {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [showLean, setShowLean] = useState(false)
  const [defs, setDefs] = useState('')
  const [root, setRoot] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nameTouched, setNameTouched] = useState(false)
  const [shelf, setShelf] = useState<PaperShelfItem[]>([])
  const [papers, setPapers] = useState<Set<string>>(new Set())
  const [showConstraints, setShowConstraints] = useState(false)
  const [axioms, setAxioms] = useState<string[]>(DEFAULT_AXIOMS)
  const [forbidden, setForbidden] = useState<string[]>([])
  const [hints, setHints] = useState<string[]>([])

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

  // live authoring check: pause typing → the pinned Lean elaborates on
  // the warm engine, diagnostics land under each buffer. Warming
  // engines retry on their own; results for stale text are orphaned.
  const [check, setCheck] = useState<{
    phase: 'idle' | 'warming' | 'checking' | 'done'
    defs: EvalDiag[]
    root: EvalDiag[]
    pre: EvalDiag[]
  }>({ phase: 'idle', defs: [], root: [], pre: [] })
  useEffect(() => {
    const hasText = defs.trim() !== '' || root.trim() !== ''
    if (!showLean || !hasText) {
      setCheck({ phase: 'idle', defs: [], root: [], pre: [] })
      return
    }
    let cancelled = false
    let retry: number | null = null
    const go = async () => {
      if (cancelled) return
      setCheck((c) => ({ ...c, phase: 'checking' }))
      try {
        const parts: { id: string; code: string }[] = []
        if (defs.trim() !== '') parts.push({ id: 'defs', code: defs })
        if (root.trim() !== '') parts.push({ id: 'root', code: root })
        const r = await evalLean(parts, [])
        if (cancelled) return
        if (r.status === 'warming') {
          setCheck((c) => ({ ...c, phase: 'warming' }))
          retry = window.setTimeout(() => void go(), 5000)
          return
        }
        setCheck({
          phase: 'done',
          defs: r.parts.defs ?? [],
          root: r.parts.root ?? [],
          pre: r.preamble,
        })
      } catch {
        if (!cancelled) setCheck({ phase: 'idle', defs: [], root: [], pre: [] })
      }
    }
    const t = window.setTimeout(() => void go(), 900)
    return () => {
      cancelled = true
      window.clearTimeout(t)
      if (retry != null) window.clearTimeout(retry)
    }
  }, [defs, root, showLean])
  const checkWord =
    check.phase === 'warming'
      ? 'engine warming — checks resume on their own'
      : check.phase === 'checking'
        ? 'checking…'
        : check.phase === 'done'
          ? countErrors([...check.pre, ...check.defs, ...check.root]) === 0
            ? '✓ elaborates'
            : `${countErrors([...check.pre, ...check.defs, ...check.root])} error${countErrors([...check.pre, ...check.defs, ...check.root]) === 1 ? '' : 's'}`
          : ''

  const nameOk = NAME_RE.test(name)
  // concrete reason, live as the user types (or after a blur): silent
  // disabled buttons make people re-read the form instead of the fix
  const nameError =
    (name !== '' || nameTouched) && !nameOk
      ? /\s/.test(name)
        ? "spaces aren't allowed — use underscores"
        : 'names are dot-separated identifiers — try Topology.my_theorem'
      : null
  const hasLean = defs.trim() !== '' || root.trim() !== ''

  const create = async () => {
    setBusy(true)
    setError(null)
    const body = `# ${name}\n\n## Statement\n\n${desc.trim()}\n`
    try {
      await apiPost<{ problem: string }>('/api/problems/create', {
        name,
        body,
        settings: {
          // whether finished work enters the Library is decided by a
          // human AT SIGN-OFF (owner: no automatic harvest) — true
          // here just raises that review gate when the problem ends
          library: true,
          axioms_whitelist: axioms,
          forbidden_lemmas: forbidden,
          lemma_hints: hints,
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
        className="mb-1 w-96 rounded-md border border-edge bg-surface px-2.5 py-1.5 font-mono text-sm text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
        placeholder="Topology.my_theorem"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onBlur={() => setNameTouched(true)}
        spellCheck={false}
        autoFocus
      />
      <div className="mb-4 min-h-4 text-[11px] text-danger">{nameError ?? ' '}</div>

      <label className="mb-1 block text-[11px] font-medium tracking-widest text-ink-faint uppercase">
        what should be proved?
      </label>
      <textarea
        className="h-64 w-full resize-y rounded-md border border-edge bg-surface p-3 text-[13px] leading-relaxed text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
        placeholder={
          'Describe the mathematics in natural language: the objects involved, the ' +
          'statements you want, any routes to prefer or avoid.\n\nExample: Compute the ' +
          'singular homology of the n-sphere with coefficients in an arbitrary ring R. ' +
          'The Mayer–Vietoris machinery is already in the Library — cite it, do not rebuild it.'
        }
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
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
                <span className="font-mono text-[10px] text-ink-faint">{p.id}</span>
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
          {check.pre.length > 0 && <DiagList diags={check.pre} />}
          <div>
            <div className="mb-1 text-[11px] text-ink-faint">
              Defs.lean — your own definitions; the engine must use these, never re-derive them.
            </div>
            <textarea
              className="h-40 w-full resize-y rounded-md border border-edge bg-surface p-3 font-mono text-xs leading-relaxed text-ink focus:border-ink-faint focus:outline-none"
              placeholder={`import Mathlib\n\nnamespace Problems.${name || '<name>'}\n\n-- your definitions\n\nend Problems.${name || '<name>'}`}
              value={defs}
              onChange={(e) => setDefs(e.target.value)}
              spellCheck={false}
            />
            <DiagList diags={check.defs} />
          </div>
          <div>
            <div className="mb-1 text-[11px] text-ink-faint">
              Root.lean — pins the exact statement that must be proved before the problem can
              finish (shape: <span className="font-mono">theorem main : &lt;stmt&gt; := by sorry</span>).
            </div>
            <textarea
              className="h-40 w-full resize-y rounded-md border border-edge bg-surface p-3 font-mono text-xs leading-relaxed text-ink focus:border-ink-faint focus:outline-none"
              placeholder={`import Mathlib\nimport Problems.${name || '<name>'}.Defs\n\nnamespace Problems.${name || '<name>'}\n\ntheorem main : <statement> := by sorry\n\nend Problems.${name || '<name>'}`}
              value={root}
              onChange={(e) => setRoot(e.target.value)}
              spellCheck={false}
            />
            <DiagList diags={check.root} />
          </div>
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
            label="lemma hints"
            hint="add Mathlib/Library name"
            values={hints}
            onChange={setHints}
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
        <pre className="mb-3 rounded-md border border-edge-strong bg-surface px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink">
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

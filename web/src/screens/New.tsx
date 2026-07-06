import { useState } from 'react'
import { apiPost } from '../lib/api'
import { navigate } from '../lib/router'
import { Button } from '../components/ui'

/*
 * Problem authoring, mathematician-first: a name, a natural-language
 * description, and sensible defaults. The frontmatter is controls, not
 * yaml; pinned Lean files stay behind an "advanced" fold. Everything
 * here can be changed later on the problem's Manifest tab.
 */

const NAME_RE = /^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*$/

export default function New() {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [library, setLibrary] = useState(true)
  const [showLean, setShowLean] = useState(false)
  const [defs, setDefs] = useState('')
  const [root, setRoot] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const nameOk = NAME_RE.test(name)
  const hasLean = defs.trim() !== '' || root.trim() !== ''

  const create = async () => {
    setBusy(true)
    setError(null)
    const body = `# ${name}\n\n## Statement\n\n${desc.trim()}\n`
    try {
      await apiPost<{ problem: string }>('/api/problems/create', {
        name,
        body,
        settings: { library },
        defs: defs.trim() === '' ? null : defs,
        root: root.trim() === '' ? null : root,
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
        onChange={(e) => setName(e.target.value.trim())}
        spellCheck={false}
        autoFocus
      />
      <div className="mb-4 text-[11px] text-ink-faint">
        {name !== '' && !nameOk
          ? 'dot-separated identifiers, e.g. Topology.my_theorem'
          : ' '}
      </div>

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

      <label className="mt-4 flex items-center gap-2 text-xs text-ink-dim">
        <input type="checkbox" checked={library} onChange={(e) => setLibrary(e.target.checked)} />
        keep finished work in the Library for reuse
      </label>

      <button
        className="mt-4 mb-2 block text-xs text-ink-dim transition-colors hover:text-ink"
        onClick={() => setShowLean((v) => !v)}
      >
        {showLean ? '▾' : '▸'} advanced — pin exact Lean (Defs.lean / Root.lean)
      </button>
      {showLean && (
        <div className="mb-3 flex flex-col gap-3">
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
          </div>
        </div>
      )}

      {error && (
        <pre className="mb-3 rounded-md border border-edge-strong bg-surface px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink">
          {error}
        </pre>
      )}

      <div className="mt-2 flex items-center gap-3">
        <Button
          variant="primary"
          disabled={busy || !nameOk || desc.trim() === ''}
          onClick={() => void create()}
        >
          {busy ? (hasLean ? 'Type-checking Lean files…' : 'Creating…') : 'Create problem'}
        </Button>
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

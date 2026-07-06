import { useState } from 'react'
import { apiPost } from '../lib/api'
import { navigate } from '../lib/router'
import { Button } from '../components/ui'

/*
 * Problem authoring — the missing half of the loop. The Manifest is
 * the human's primary input to the engine; this form writes it and
 * runs the same init chokepoint as `asterism init`. Pure-NL creation
 * is instant; pinned Defs/Root type-check first (lake build).
 */

const TEMPLATE = (name: string) => `---
problem: ${name || '<Namespace.leaf_name>'}
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# ${name || '<Namespace.leaf_name>'} — <one-line title>

## Statement

Describe what you want in natural language: the objects to define and
the claims to prove. The Strategist derives everything from this
Manifest unless you pin Defs/Root below.

### Deliverables

- \`my_top_level_claim\` — the top-level statement you will vouch for.

## Strategic notes

Optional: constraints, preferred routes, forbidden angles.
`

const NAME_RE = /^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*$/

export default function New() {
  const [name, setName] = useState('')
  const [manifest, setManifest] = useState('')
  const [touched, setTouched] = useState(false)
  const [showLean, setShowLean] = useState(false)
  const [defs, setDefs] = useState('')
  const [root, setRoot] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const nameOk = NAME_RE.test(name)
  const body = touched ? manifest : TEMPLATE(name)
  const hasLean = defs.trim() !== '' || root.trim() !== ''

  const create = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiPost<{ problem: string }>('/api/problems/create', {
        name,
        manifest: body,
        defs: defs.trim() === '' ? null : defs,
        root: root.trim() === '' ? null : root,
      })
      // suggest the scope on the Engine page so "start it" is one click
      localStorage.setItem('engine_scope_suggest', name)
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
        The Manifest is your instruction to the engine. Name the problem, say what you want
        in natural language, and the Strategist takes it from there. Pinning Lean files is
        optional: Defs.lean pre-vouches your vocabulary, Root.lean pins the exact exit
        statement.
      </p>

      <label className="mb-1 block text-[11px] font-medium tracking-widest text-ink-faint uppercase">
        name
      </label>
      <input
        className="mb-1 w-96 rounded-md border border-edge bg-surface px-2.5 py-1.5 font-mono text-sm text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
        placeholder="Namespace.leaf_name"
        value={name}
        onChange={(e) => setName(e.target.value.trim())}
        spellCheck={false}
        autoFocus
      />
      <div className="mb-4 text-[11px] text-ink-faint">
        {name !== '' && !nameOk
          ? 'dot-separated identifiers, e.g. Topology.my_theorem'
          : name !== ''
            ? `→ Problems/${name.split('.').join('/')}/Manifest.md`
            : ' '}
      </div>

      <label className="mb-1 block text-[11px] font-medium tracking-widest text-ink-faint uppercase">
        manifest
      </label>
      <textarea
        className="h-96 w-full resize-y rounded-md border border-edge bg-surface p-3 font-mono text-xs leading-relaxed text-ink focus:border-ink-faint focus:outline-none"
        value={body}
        onChange={(e) => {
          setTouched(true)
          setManifest(e.target.value)
        }}
        spellCheck={false}
      />

      <button
        className="mt-3 mb-2 block text-xs text-ink-dim transition-colors hover:text-ink"
        onClick={() => setShowLean((v) => !v)}
      >
        {showLean ? '▾' : '▸'} pin Lean files (optional — Defs.lean / Root.lean)
      </button>
      {showLean && (
        <div className="mb-3 flex flex-col gap-3">
          <div>
            <div className="mb-1 text-[11px] text-ink-faint">
              Defs.lean — author-vouched vocabulary the engine must cite, never re-derive.
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
              exit (canonical shape: <span className="font-mono">theorem main : &lt;stmt&gt; := by sorry</span>).
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

      <div className="flex items-center gap-3">
        <Button variant="primary" disabled={busy || !nameOk || body.trim() === ''} onClick={() => void create()}>
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

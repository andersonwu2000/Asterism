import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import { Link } from '../lib/router'
import { Button } from './ui'
import type { ManifestData } from '../lib/types'

/*
 * The Manifest as the user's instrument: settings are controls, the
 * body is natural language. Hot-reload means a save applies to the
 * running engine on its next tick. Manual edits lock while a
 * strategist amend is pending — two writers, one file.
 */

function ListField({
  label,
  hint,
  values,
  onChange,
}: {
  label: string
  hint: string
  values: string[]
  onChange: (v: string[]) => void
}) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const v = draft.trim()
    if (v !== '' && !values.includes(v)) onChange([...values, v])
    setDraft('')
  }
  return (
    <div>
      <div className="mb-1 text-[11px] font-medium tracking-widest text-ink-faint uppercase">
        {label}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {values.map((v) => (
          <span
            key={v}
            className="group flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-dim"
          >
            {v}
            <button
              className="text-ink-faint transition-colors hover:text-ink"
              title={`remove ${v}`}
              onClick={() => onChange(values.filter((x) => x !== v))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="w-44 rounded border border-edge bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
          placeholder={hint}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') add()
          }}
          onBlur={add}
        />
      </div>
    </div>
  )
}

export default function ManifestEditor({
  problem,
  onDirtyChange,
}: {
  problem: string
  onDirtyChange?: (dirty: boolean) => void
}) {
  const [data, setData] = useState<ManifestData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [body, setBody] = useState('')
  const [settings, setSettings] = useState<ManifestData['settings'] | null>(null)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)

  // the parent shows an unsaved-changes dot on the tab
  useEffect(() => {
    onDirtyChange?.(dirty)
  }, [dirty, onDirtyChange])

  // an unsaved draft must survive an accidental reload/close
  useEffect(() => {
    if (!dirty) return
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [dirty])

  useEffect(() => {
    let cancelled = false
    apiGet<ManifestData>(`/api/problems/${encodeURIComponent(problem)}/manifest`)
      .then((d) => {
        if (cancelled) return
        setData(d)
        setBody(d.body)
        setSettings(d.settings)
      })
      .catch((e) => !cancelled && setError(String((e as Error).message)))
    return () => {
      cancelled = true
    }
  }, [problem])

  if (error) return <div className="p-6 text-xs text-ink-dim">{error}</div>
  if (!data || !settings)
    return <div className="late-fade p-6 text-xs text-ink-faint">Loading…</div>

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiPost(`/api/problems/${encodeURIComponent(problem)}/manifest`, {
        body,
        settings,
      })
      setDirty(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  const touch = () => {
    setDirty(true)
    setSaved(false)
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-5">
      {data.pending_amend && (
        <div className="mb-4 rounded-md border border-warn/50 bg-warn/10 px-3 py-2 text-xs text-warn">
          The strategist has a pending amend request on this Manifest — editing is locked so
          the two changes don't collide.{' '}
          <Link to="/inbox" className="underline">
            Resolve it in the Inbox
          </Link>
          .
        </div>
      )}
      <fieldset disabled={data.pending_amend} className="flex flex-col gap-4">
        <div>
          <div className="mb-1 text-[11px] font-medium tracking-widest text-ink-faint uppercase">
            instructions — natural language, hot-reloaded
          </div>
          <textarea
            className="h-96 w-full resize-y rounded-md border border-edge bg-surface p-3 font-mono text-xs leading-relaxed text-ink focus:border-ink-faint focus:outline-none disabled:opacity-60"
            value={body}
            onChange={(e) => {
              setBody(e.target.value)
              touch()
            }}
            spellCheck={false}
          />
        </div>
        <label className="flex items-center gap-2 text-xs text-ink-dim">
          <input
            type="checkbox"
            checked={settings.library}
            onChange={(e) => {
              setSettings({ ...settings, library: e.target.checked })
              touch()
            }}
          />
          harvest finished work into the Library
        </label>
        <ListField
          label="forbidden lemmas"
          hint="add pattern (e.g. sperner*)"
          values={settings.forbidden_lemmas}
          onChange={(v) => {
            setSettings({ ...settings, forbidden_lemmas: v })
            touch()
          }}
        />
        <ListField
          label="lemma hints"
          hint="add Mathlib/Library name"
          values={settings.lemma_hints}
          onChange={(v) => {
            setSettings({ ...settings, lemma_hints: v })
            touch()
          }}
        />
        <ListField
          label="axiom whitelist"
          hint="add axiom"
          values={settings.axioms_whitelist}
          onChange={(v) => {
            setSettings({ ...settings, axioms_whitelist: v })
            touch()
          }}
        />
        <div className="flex items-center gap-3">
          <Button variant="primary" disabled={busy || !dirty} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </Button>
          {saved && <span className="text-[11px] text-ink-faint">saved — the engine picks it up on its next tick</span>}
          {error && <span className="text-[11px] text-ink-dim">{error}</span>}
        </div>
      </fieldset>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { apiDelete, apiGet, apiPost } from '../lib/api'
import { Link } from '../lib/router'
import { Button, Select } from './ui'
import ListField from './ListField'
import { MarkdownEditor } from '../lib/markdown'
import type { ManifestData, PaperShelfItem, ProblemPaperBinding } from '../lib/types'

/*
 * The Manifest as the user's instrument: settings are controls, the
 * body is natural language. Hot-reload means a save applies to the
 * running engine on its next tick. Manual edits lock while a
 * strategist amend is pending — two writers, one file.
 */

/** Papers bound to this problem. Bindings live in the DB, not in
 * Manifest.md, so this block deliberately sits OUTSIDE the
 * pending_amend fieldset lock — binding a paper never collides with a
 * strategist amend. */
function PapersBlock({ problem }: { problem: string }) {
  const [bindings, setBindings] = useState<ProblemPaperBinding[] | null>(null)
  const [shelf, setShelf] = useState<PaperShelfItem[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [pick, setPick] = useState('')
  const [busy, setBusy] = useState(false)
  const [tick, setTick] = useState(0)
  const refresh = () => setTick((t) => t + 1)

  useEffect(() => {
    let cancelled = false
    apiGet<{ papers: ProblemPaperBinding[] }>(
      `/api/problems/${encodeURIComponent(problem)}/papers`,
    )
      .then((d) => {
        if (cancelled) return
        setBindings(d.papers)
        setErr(null)
      })
      .catch((e) => !cancelled && setErr(String((e as Error).message)))
    apiGet<{ papers: PaperShelfItem[] }>('/api/papers')
      .then((d) => !cancelled && setShelf(d.papers))
      .catch(() => {
        /* shelf unavailable → the bind select simply stays empty */
      })
    return () => {
      cancelled = true
    }
  }, [problem, tick])

  const unbind = async (pid: string) => {
    setBusy(true)
    try {
      await apiDelete(`/api/problems/${encodeURIComponent(problem)}/papers/${pid}`)
      refresh()
    } catch (e) {
      setErr(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }
  const bind = async () => {
    if (pick === '') return
    setBusy(true)
    try {
      await apiPost(`/api/problems/${encodeURIComponent(problem)}/papers`, { paper_id: pick })
      setPick('')
      refresh()
    } catch (e) {
      setErr(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  const boundIds = new Set((bindings ?? []).map((b) => b.id))
  const bindable = shelf.filter((s) => !boundIds.has(s.id))

  return (
    <div className="mt-6">
      <div className="mb-1 text-[11px] font-medium tracking-widest text-ink-faint uppercase">
        papers
      </div>
      <p className="mb-2 text-[11px] text-ink-faint">
        the engine reads bound papers for definitions and proof routes — bindings apply even
        while an amend locks the editor above
      </p>
      {bindings === null && err === null ? (
        <div className="late-fade text-xs text-ink-faint">Loading…</div>
      ) : bindings !== null && bindings.length === 0 ? (
        <div className="text-xs text-ink-faint">
          no papers bound — the engine works from the description alone
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {(bindings ?? []).map((b) => (
            <div key={b.id} className="flex items-center gap-2" title={b.reason ?? undefined}>
              {b.missing ? (
                <>
                  <span className="font-mono text-[12px] text-ink-dim">
                    {b.source_name ?? b.id}
                  </span>
                  <span className="text-[11px] text-danger">shelf entry missing</span>
                </>
              ) : (
                <Link
                  to={`/papers/${encodeURIComponent(b.id)}`}
                  className="font-mono text-[12px] text-ink transition-colors hover:text-starlight"
                  title={b.reason ?? `read ${b.source_name ?? b.id}`}
                >
                  {b.source_name ?? b.id}
                </Link>
              )}
              <span
                className="text-[10px] text-ink-faint"
                title={
                  b.origin === 'scholar'
                    ? 'fetched by the engine during a run'
                    : b.origin === 'manifest'
                      ? 'bound when the problem was created'
                      : 'bound by you'
                }
              >
                {b.origin}
              </span>
              <button
                className="text-ink-faint transition-colors hover:text-ink disabled:opacity-45"
                disabled={busy}
                title="unbind this paper from the problem (the shelf copy stays)"
                onClick={() => void unbind(b.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      {bindable.length > 0 && (
        <div className="mt-2 flex items-center gap-2">
          <Select className="w-72 shrink-0" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">bind a paper from the shelf…</option>
            {bindable.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title ?? s.source_name}
              </option>
            ))}
          </Select>
          {pick !== '' && (
            <Button variant="outline" size="xs" disabled={busy} onClick={() => void bind()}>
              bind
            </Button>
          )}
        </div>
      )}
      {err && <div className="mt-1 text-[11px] text-ink-dim">{err}</div>}
    </div>
  )
}

export default function ManifestEditor({
  problem,
  onDirtyChange,
  bridged = false,
}: {
  problem: string
  onDirtyChange?: (dirty: boolean) => void
  /** work already in the Library — the `library` flag is settled */
  bridged?: boolean
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

  if (error)
    return (
      <div className="p-6 text-xs text-ink-dim">
        {/* raw "404: no Manifest.md" is machine voice — say what it
            means and what to do (a problem row whose folder was moved
            or reset; audit 2026-07-11) */}
        {/404|no Manifest/i.test(error)
          ? 'This problem has no Manifest.md on disk — its folder was likely moved or reset. Re-create the file, or delete the problem below.'
          : error}
      </div>
    )
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
        <div className="mb-4 rounded-lg border border-warn/50 bg-warn/10 px-3 py-2 text-xs text-warn">
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
          <div
            className="mb-1 text-[11px] font-medium tracking-widest text-ink-faint uppercase"
            title="engine term: hot-reloaded — a save takes effect at the next agent launch; nothing restarts"
          >
            instructions — plain language; saves apply from the next agent onward
          </div>
          <MarkdownEditor
            value={body}
            onChange={(v) => {
              setBody(v)
              touch()
            }}
          />
        </div>
        <label
          className={`flex items-center gap-2 text-xs text-ink-dim ${bridged ? 'opacity-60' : ''}`}
          title={bridged ? "settled — this problem's work is already in the Library" : undefined}
        >
          <input
            type="checkbox"
            checked={settings.library}
            disabled={bridged}
            onChange={(e) => {
              setSettings({ ...settings, library: e.target.checked })
              touch()
            }}
          />
          harvest finished work into the Library
          {bridged && <span className="text-[10px] text-ink-faint">· settled — already in the Library</span>}
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
        {/* the axiom gate is FIXED AT CREATION (server enforces 409):
            the gate re-reads it per validation, so a mid-life edit
            would re-tune soundness under live proofs — display only */}
        <div>
          <div className="mb-1 flex items-baseline gap-2 text-[11px] font-medium tracking-widest text-ink-faint uppercase">
            axiom whitelist
            <span className="font-normal tracking-normal normal-case">
              — fixed when the problem is created; set it on the New problem form
            </span>
          </div>
          {settings.axioms_whitelist.length === 0 ? (
            <span className="text-xs text-ink-faint">
              empty — the gate admits nothing beyond the kernel's defaults
            </span>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {settings.axioms_whitelist.map((a) => (
                <span
                  key={a}
                  className="rounded-full border border-edge bg-surface px-2 py-0.5 font-mono text-[11px] text-ink-dim"
                >
                  {a}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Button variant="primary" disabled={busy || !dirty} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </Button>
          {saved && <span className="text-[11px] text-ink-faint">saved — the engine picks it up on its next tick</span>}
          {error && <span className="text-[11px] text-ink-dim">{error}</span>}
        </div>
      </fieldset>
      {/* NOTE: outside the fieldset on purpose — paper bindings are DB
          rows, not Manifest.md content, so the pending_amend lock does
          not apply to them */}
      <PapersBlock problem={problem} />
    </div>
  )
}

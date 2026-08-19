import { useEffect, useState } from 'react'
import { apiDelete, apiGet, apiPost } from '../lib/api'
import { Link } from '../lib/router'
import { Button, Select } from './ui'
import ListField from './ListField'
import { MarkdownEditor } from '../lib/markdown'
import type { IntentData, PaperShelfItem, ProblemPaperBinding } from '../lib/types'

/*
 * What the HUMAN asked, as the user's instrument (v40 — Manifest.md
 * retired, the intent lives in the engine's own DB): the GOAL, the
 * standing WORD, and the machine settings. Each reaches the running
 * engine on its next tick.
 *
 * The two halves are not the same kind of thing, which is the whole
 * reason they were split: the goal is the claim to settle and the
 * engine may PROPOSE a change to it (that proposal locks the goal
 * until you answer it in the Inbox), while the word is yours alone —
 * carried verbatim into every agent at every depth, never
 * machine-amendable, and so it never locks.
 */

/** Papers bound to this problem. A binding is its own DB row, not part
 * of the goal, so this block deliberately sits OUTSIDE the
 * pending_amend lock — binding a paper never collides with a
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
      <div
        className="mb-2 text-[11px] font-medium tracking-widest text-ink-faint uppercase"
        title="the engine reads bound papers for definitions and proof routes. A binding is its own row, not part of the goal, so it keeps working even while a pending amend locks the goal above."
      >
        papers
      </div>
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

export default function IntentEditor({
  problem,
  onDirtyChange,
  bridged = false,
}: {
  problem: string
  onDirtyChange?: (dirty: boolean) => void
  /** work already in the Library — the `library` flag is settled */
  bridged?: boolean
}) {
  const [data, setData] = useState<IntentData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [charter, setCharter] = useState('')
  const [word, setWord] = useState('')
  const [settings, setSettings] = useState<IntentData['settings'] | null>(null)
  // per FIELD, not one flag: every sanctioned write records a history
  // row and re-mirrors the durable seed, so posting a field nobody
  // touched would file a change that never happened
  const [touched, setTouched] = useState<Set<'charter' | 'word' | 'settings'>>(new Set())
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const dirty = touched.size > 0

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
    apiGet<IntentData>(`/api/problems/${encodeURIComponent(problem)}/intent`)
      .then((d) => {
        if (cancelled) return
        setData(d)
        setCharter(d.charter)
        setWord(d.word)
        setSettings(d.settings)
      })
      .catch((e) => !cancelled && setError(String((e as Error).message)))
    return () => {
      cancelled = true
    }
  }, [problem])

  if (error && !data)
    return (
      <div className="p-6 text-xs text-ink-dim">
        {/* raw "404: unknown problem" is machine voice — say what it
            means and what to do (a problem the engine no longer knows;
            audit 2026-07-11) */}
        {/404|unknown problem|no DB/i.test(error)
          ? 'The engine does not know this problem — it was likely reset or removed. Create it again, or delete the row below.'
          : error}
      </div>
    )
  if (!data || !settings)
    return <div className="late-fade p-6 text-xs text-ink-faint">Loading…</div>

  const touch = (what: 'charter' | 'word' | 'settings') => {
    setTouched((old) => new Set(old).add(what))
    setSaved(false)
  }

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiPost(`/api/problems/${encodeURIComponent(problem)}/intent`, {
        ...(touched.has('charter') ? { charter } : {}),
        ...(touched.has('word') ? { word } : {}),
        // only the two knobs this panel OWNS. The read carries more
        // than that (the axiom gate, which is read-only, and machine
        // channels this UI never shows) and writing a value back
        // merely because it was read is how a surface starts
        // asserting settings nobody chose here.
        ...(touched.has('settings')
          ? {
              settings: {
                library: settings.library,
                forbidden_lemmas: settings.forbidden_lemmas,
              },
            }
          : {}),
      })
      setTouched(new Set())
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setError(String((e as Error).message))
    } finally {
      setBusy(false)
    }
  }

  const eyebrow = 'mb-1.5 text-[11px] font-medium tracking-widest text-ink-faint uppercase'

  return (
    <div className="mx-auto max-w-4xl px-6 py-5">
      {data.pending_amend && (
        <div className="mb-4 rounded-lg border border-warn/50 bg-warn/10 px-3 py-2 text-xs text-warn">
          The strategist has proposed a change to this goal — editing it is locked so the two
          changes don't collide.{' '}
          <Link to="/inbox" className="underline">
            Resolve it in the Inbox
          </Link>
          .
        </div>
      )}
      <div className="flex flex-col gap-5">
        {/* THE GOAL — the engine may propose a change to it, so it locks */}
        <fieldset disabled={data.pending_amend}>
          <div
            className={eyebrow}
            title="engine term: the top group's charter — every group, this one included, is judged against its charter and nothing else"
          >
            the goal
          </div>
          <MarkdownEditor
            value={charter}
            onChange={(v) => {
              setCharter(v)
              touch('charter')
            }}
          />
        </fieldset>

        {/* YOUR WORD — the machine reads it and never writes it, so it
            stays editable even while an amend is pending */}
        <div>
          <div
            className={eyebrow}
            title="carried verbatim into every agent at every depth of the discussion tree. The engine has no way to amend it — there is no request it can make against your word."
          >
            your standing word
          </div>
          <MarkdownEditor
            heightClass="h-64"
            value={word}
            onChange={(v) => {
              setWord(v)
              touch('word')
            }}
          />
          <div className="mt-1 text-[11px] text-ink-faint">
            what holds however the goal is rewritten — routes to prefer or avoid, standards to
            keep. Empty is fine.
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="primary" disabled={busy || !dirty} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </Button>
          <span className="text-[11px] text-ink-faint">
            {saved
              ? 'saved — the engine picks it up on its next tick'
              : 'plain language; a save reaches the next agent, nothing restarts'}
          </span>
          {error && <span className="text-[11px] text-ink-dim">{error}</span>}
        </div>

        <fieldset
          disabled={data.pending_amend}
          className="flex flex-col gap-2.5 rounded-xl border border-edge bg-surface px-3.5 py-3"
        >
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
                touch('settings')
              }}
            />
            harvest finished work into the Library
            {bridged && (
              <span className="text-[10px] text-ink-faint">· already in the Library</span>
            )}
          </label>
          <ListField
            inline
            label="forbidden lemmas"
            hint="add pattern (e.g. sperner*)"
            values={settings.forbidden_lemmas}
            onChange={(v) => {
              setSettings({ ...settings, forbidden_lemmas: v })
              touch('settings')
            }}
          />
          {/* the axiom gate is FIXED AT CREATION (server enforces 409):
              the gate re-reads it per validation, so a mid-life edit
              would re-tune soundness under live proofs. Read-only, so
              it reads as a fact, not as a control you may not touch */}
          <div
            className="flex flex-wrap items-center gap-2"
            title="fixed when the problem is created — the gate re-reads it on every validation, so changing it mid-life would re-tune soundness under proofs that already passed. Set it on the New problem form."
          >
            <span className="w-40 shrink-0 text-xs text-ink-dim">axioms admitted</span>
            <span className="font-mono text-[11px] text-ink-faint">
              {settings.axioms_whitelist.length === 0
                ? "the kernel's defaults, nothing more"
                : settings.axioms_whitelist.join(' · ')}
            </span>
          </div>
        </fieldset>
      </div>
      {/* NOTE: outside the lock on purpose — paper bindings are their own
          DB rows, not part of the goal, so a pending amend does not
          apply to them */}
      <PapersBlock problem={problem} />
    </div>
  )
}

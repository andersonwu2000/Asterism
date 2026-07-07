import { useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { Button } from '../components/ui'

/*
 * The setup wizard — the bootstrap's second half, in the browser
 * (owner's calls: browser wizard over a native one; detect an
 * existing Lean rather than install a second; pick the drive the
 * multi-GB toolchain lands on; Windows first). Not a forced linear
 * flow: a checklist of components, each with its state and its one
 * action. Everything is safe to retry.
 */

interface SetupStatus {
  repo: string
  platform: string
  lake: { found: boolean; path: string | null; version: string | null }
  mathlib: { present: boolean }
  claude: { installed: boolean; logged_in: boolean }
  elan_home: string
  disks: { mount: string; free_gb: number; total_gb: number }[]
  update: null
}

interface Job {
  state: 'idle' | 'running' | 'done' | 'failed'
  log: string[]
  rc?: number
}

/** poll a named job while it runs; returns state + live log tail */
function useJob(name: string, active: boolean): Job {
  const { data } = usePoll<Job>(active ? `/api/setup/job/${name}` : null, 1500)
  return data ?? { state: 'idle', log: [] }
}

function StatusDot({ ok, busy = false }: { ok: boolean; busy?: boolean }) {
  return (
    <span
      className={`h-2 w-2 shrink-0 rounded-full ${
        busy ? 'bg-accent animate-pulse' : ok ? 'bg-ok' : 'bg-warn'
      }`}
      aria-hidden
    />
  )
}

function Card({
  ok,
  busy = false,
  title,
  children,
}: {
  ok: boolean
  busy?: boolean
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-edge bg-surface p-4">
      <div className="mb-2 flex items-center gap-2.5">
        <StatusDot ok={ok} busy={busy} />
        <span className="text-sm font-medium text-ink">{title}</span>
      </div>
      {children}
    </div>
  )
}

function JobLog({ job }: { job: Job }) {
  const ref = useRef<HTMLPreElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [job.log])
  if (job.state === 'idle' || job.log.length === 0) return null
  return (
    <pre
      ref={ref}
      className="mt-2 max-h-40 overflow-y-auto rounded-md border border-edge bg-bg px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink-dim"
    >
      {job.log.join('\n')}
    </pre>
  )
}

export default function Setup() {
  const { data: st, refresh } = usePoll<SetupStatus>('/api/setup/status', 4000)
  const [err, setErr] = useState<string | null>(null)

  // Lean card state
  const [leanMode, setLeanMode] = useState<'install' | 'existing'>('install')
  const [elanHome, setElanHome] = useState<string | null>(null)
  const [lakePath, setLakePath] = useState('')
  const [leanBusy, setLeanBusy] = useState(false)
  const leanJob = useJob('lean', true)
  const mathlibJob = useJob('mathlib', true)
  const claudeJob = useJob('claude', true)

  if (!st) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>

  const repoDrive = st.repo.slice(0, 3)
  const repoDisk = st.disks.find((d) => st.repo.toLowerCase().startsWith(d.mount.toLowerCase()))
  const allDone = st.lake.found && st.mathlib.present && st.claude.installed && st.claude.logged_in

  const act = async (path: string, body?: unknown) => {
    setErr(null)
    try {
      await apiPost(path, body ?? {})
    } catch (e) {
      setErr(String((e as Error).message))
    } finally {
      refresh()
    }
  }

  const submitLakePath = async () => {
    setLeanBusy(true)
    setErr(null)
    try {
      await apiPost('/api/setup/lake-path', { path: lakePath })
      refresh()
    } catch (e) {
      setErr(String((e as Error).message))
    } finally {
      setLeanBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="font-display text-[26px] font-medium text-ink">Set up Asterism</h1>
      <p className="mt-1 max-w-[64ch] text-xs text-ink-faint">
        Four components, each safe to retry. Green all the way down means the engine is ready —
        nothing here needs a terminal.
      </p>
      {err && <div className="mt-3 text-xs text-warn">{err}</div>}

      <div className="mt-6 flex flex-col gap-4">
        {/* 1 — where Asterism lives */}
        <Card ok title="Asterism itself">
          <div className="text-xs text-ink-dim">
            installed at <span className="font-mono text-ink">{st.repo}</span>
            {repoDisk && (
              <span className="tnum ml-2 text-ink-faint">
                ({repoDisk.free_gb} GB free on {repoDrive})
              </span>
            )}
          </div>
          <p className="mt-1 text-[11px] text-ink-faint">
            To move it: close Asterism, move the whole folder, run installer\install.bat once
            from the new place.
          </p>
        </Card>

        {/* 2 — Lean */}
        <Card
          ok={st.lake.found}
          busy={leanJob.state === 'running'}
          title="Lean theorem prover"
        >
          {st.lake.found ? (
            <div className="text-xs text-ink-dim">
              <span className="text-ok">found</span> ·{' '}
              <span className="font-mono">{st.lake.version}</span>
              <div className="mt-0.5 truncate font-mono text-[11px] text-ink-faint">
                {st.lake.path}
              </div>
            </div>
          ) : (
            <>
              <div className="mb-2 flex gap-4 text-xs">
                <label className="flex cursor-pointer items-center gap-1.5 text-ink-dim">
                  <input
                    type="radio"
                    checked={leanMode === 'install'}
                    onChange={() => setLeanMode('install')}
                  />
                  install it for me
                </label>
                <label className="flex cursor-pointer items-center gap-1.5 text-ink-dim">
                  <input
                    type="radio"
                    checked={leanMode === 'existing'}
                    onChange={() => setLeanMode('existing')}
                  />
                  I already have Lean
                </label>
              </div>
              {leanMode === 'install' ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] text-ink-faint">install to drive</span>
                  <select
                    className="rounded border border-edge bg-bg px-2 py-1 font-mono text-xs text-ink focus:outline-none"
                    value={elanHome ?? st.elan_home}
                    onChange={(e) => setElanHome(e.target.value)}
                  >
                    <option value={st.elan_home}>{st.elan_home} (default)</option>
                    {st.disks
                      .filter((d) => !st.elan_home.toLowerCase().startsWith(d.mount.toLowerCase()))
                      .map((d) => (
                        <option key={d.mount} value={`${d.mount}elan`}>
                          {d.mount}elan ({d.free_gb} GB free)
                        </option>
                      ))}
                  </select>
                  <Button
                    variant="primary"
                    disabled={leanJob.state === 'running'}
                    onClick={() =>
                      void act('/api/setup/install-lean', { elan_home: elanHome ?? st.elan_home })
                    }
                  >
                    {leanJob.state === 'running' ? 'Installing…' : 'Install Lean'}
                  </Button>
                  <span className="text-[11px] text-ink-faint">~1 GB, a few minutes</span>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    className="w-96 rounded border border-edge bg-bg px-2 py-1 font-mono text-xs text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
                    placeholder="path to lake.exe or its folder (e.g. C:\Users\me\.elan\bin)"
                    value={lakePath}
                    onChange={(e) => setLakePath(e.target.value)}
                  />
                  <Button variant="primary" disabled={leanBusy || lakePath === ''} onClick={() => void submitLakePath()}>
                    {leanBusy ? 'Checking…' : 'Use this Lean'}
                  </Button>
                </div>
              )}
              <JobLog job={leanJob} />
            </>
          )}
        </Card>

        {/* 3 — Mathlib cache */}
        <Card
          ok={st.mathlib.present}
          busy={mathlibJob.state === 'running'}
          title="Math library (Mathlib)"
        >
          {st.mathlib.present ? (
            <div className="text-xs text-ink-dim">
              <span className="text-ok">ready</span> — the prebuilt cache is in place
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="primary"
                  disabled={!st.lake.found || mathlibJob.state === 'running'}
                  onClick={() => void act('/api/setup/fetch-mathlib')}
                  title={st.lake.found ? undefined : 'install Lean first'}
                >
                  {mathlibJob.state === 'running' ? 'Fetching…' : 'Fetch the math library'}
                </Button>
                <span className="text-[11px] text-ink-faint">
                  several GB, lands next to Asterism on {repoDrive}
                  {repoDisk && ` (${repoDisk.free_gb} GB free)`} — one time; leave this page open
                </span>
              </div>
              <JobLog job={mathlibJob} />
            </>
          )}
        </Card>

        {/* 4 — Claude Code */}
        <Card
          ok={st.claude.installed && st.claude.logged_in}
          busy={claudeJob.state === 'running'}
          title="Claude Code (the AI that writes the proofs)"
        >
          {!st.claude.installed ? (
            <>
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  disabled={claudeJob.state === 'running'}
                  onClick={() => void act('/api/setup/install-claude')}
                >
                  {claudeJob.state === 'running' ? 'Installing…' : 'Install Claude Code'}
                </Button>
              </div>
              <JobLog job={claudeJob} />
            </>
          ) : !st.claude.logged_in ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-ink-dim">installed — one login left</span>
              <Button variant="primary" onClick={() => void act('/api/claude/login')}>
                Open the login window
              </Button>
            </div>
          ) : (
            <div className="text-xs text-ink-dim">
              <span className="text-ok">installed and logged in</span> — your Claude
              subscription pays for the proving
            </div>
          )}
        </Card>
      </div>

      <div className="mt-8 flex items-center gap-3">
        {allDone ? (
          <>
            <Link
              to="/"
              className="rounded-md bg-star px-4 py-2 text-sm font-medium text-bg transition-opacity hover:opacity-90"
            >
              Everything's ready — open the Board
            </Link>
            <span className="text-[11px] text-ink-faint">
              create a problem, press Run, watch the sky
            </span>
          </>
        ) : (
          <span className="text-[11px] text-ink-faint">
            this page keeps itself up to date — finish the yellow cards above in any order
          </span>
        )}
      </div>
    </div>
  )
}

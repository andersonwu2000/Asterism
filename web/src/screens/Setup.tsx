import { useEffect, useRef, useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { Button } from '../components/ui'

/*
 * The setup wizard — the bootstrap's second half, in the browser
 * (owner's calls: browser wizard over a native one; detect an
 * existing Lean rather than install a second; pick the drive the
 * multi-GB toolchain lands on; Windows first; decisions are collected
 * UP FRONT so the whole install runs unattended after one click —
 * nothing discovers a missing answer while the user is away).
 *
 * Shape: a decisions card (only the questions that still matter),
 * one primary button, then a progress card — component checklist +
 * the live log of the one-click job. The login is the single step
 * that needs a human; its window opens early (Claude installs first)
 * and its row stays yellow until done.
 */

interface SetupStatus {
  repo: string
  platform: string
  lake: { found: boolean; path: string | null; version: string | null }
  mathlib: { present: boolean }
  git: { found: boolean }
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

function JobLog({ job }: { job: Job }) {
  const ref = useRef<HTMLPreElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [job.log])
  if (job.state === 'idle' || job.log.length === 0) return null
  return (
    <pre
      ref={ref}
      className="mt-3 max-h-64 overflow-y-auto rounded-md border border-edge bg-bg px-3 py-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink-dim"
    >
      {job.log.join('\n')}
    </pre>
  )
}

/** one row of the progress checklist */
function StepRow({
  ok,
  busy = false,
  title,
  detail,
  children,
}: {
  ok: boolean
  busy?: boolean
  title: string
  detail?: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-2.5 py-1.5">
      <span className="mt-1"><StatusDot ok={ok} busy={busy} /></span>
      <div className="min-w-0 flex-1">
        <span className="text-sm text-ink">{title}</span>
        {detail && <span className="ml-2 text-xs text-ink-faint">{detail}</span>}
        {children}
      </div>
    </div>
  )
}

export default function Setup() {
  const { data: st, refresh } = usePoll<SetupStatus>('/api/setup/status', 4000)
  const [err, setErr] = useState<string | null>(null)

  // decisions (collected before the run starts)
  const [leanMode, setLeanMode] = useState<'install' | 'existing'>('install')
  const [elanHome, setElanHome] = useState<string | null>(null)
  const [lakePath, setLakePath] = useState('')
  const [starting, setStarting] = useState(false)

  const job = useJob('all', true)

  if (!st) return <div className="late-fade p-8 text-sm text-ink-faint">Loading…</div>

  const repoDrive = st.repo.slice(0, 3)
  const repoDisk = st.disks.find((d) => st.repo.toLowerCase().startsWith(d.mount.toLowerCase()))
  const allDone =
    st.lake.found && st.mathlib.present && st.git.found && st.claude.installed && st.claude.logged_in
  const running = job.state === 'running'
  const anythingStarted = job.state !== 'idle' || st.lake.found || st.mathlib.present || st.claude.installed
  // which decisions still matter
  const needsLeanDecision = !st.lake.found

  const startAll = async () => {
    setErr(null)
    setStarting(true)
    try {
      await apiPost('/api/setup/run-all', {
        lean_mode: needsLeanDecision ? leanMode : 'auto',
        elan_home: elanHome ?? st.elan_home,
        lake_path: leanMode === 'existing' ? lakePath : null,
      })
    } catch (e) {
      setErr(String((e as Error).message))
    } finally {
      setStarting(false)
      refresh()
    }
  }

  const openLogin = () => void apiPost('/api/claude/login', {}).catch((e) => setErr(String(e.message)))

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="font-display text-[26px] font-medium text-ink">Set up Asterism</h1>
      <p className="mt-1 max-w-[64ch] text-xs text-ink-faint">
        Answer what's below, press the button, walk away. The one thing that needs you is the
        Claude login — a browser tab opens in the first minute; click Authorize.
      </p>
      {err && <div className="mt-3 text-xs text-warn">{err}</div>}

      {/* ------------------------------------------------ decisions */}
      {!allDone && (
        <div className="mt-6 rounded-lg border border-edge bg-surface p-4">
          <div className="text-sm font-medium text-ink">Before it runs</div>

          <div className="mt-2 text-xs text-ink-dim">
            Asterism lives at <span className="font-mono text-ink">{st.repo}</span>
            {repoDisk && (
              <span className="tnum ml-2 text-ink-faint">
                — the math library (~5 GB) lands there too ({repoDisk.free_gb} GB free on {repoDrive})
              </span>
            )}
          </div>

          {needsLeanDecision ? (
            <div className="mt-3">
              <div className="mb-2 flex gap-4 text-xs">
                <label className="flex cursor-pointer items-center gap-1.5 text-ink-dim">
                  <input
                    type="radio"
                    checked={leanMode === 'install'}
                    onChange={() => setLeanMode('install')}
                  />
                  install Lean for me
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
                  <span className="text-[11px] text-ink-faint">Lean toolchain (~1 GB) goes to</span>
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
                </div>
              ) : (
                <input
                  className="w-96 rounded border border-edge bg-bg px-2 py-1 font-mono text-xs text-ink placeholder:font-sans placeholder:text-ink-faint focus:border-ink-faint focus:outline-none"
                  placeholder="path to lake.exe or its folder (e.g. C:\Users\me\.elan\bin)"
                  value={lakePath}
                  onChange={(e) => setLakePath(e.target.value)}
                />
              )}
            </div>
          ) : (
            <div className="mt-2 text-xs text-ink-dim">
              Lean: <span className="text-ok">found</span> ·{' '}
              <span className="font-mono">{st.lake.version}</span>
            </div>
          )}

          <div className="mt-4 flex items-center gap-3">
            <Button
              variant="primary"
              disabled={running || starting || (leanMode === 'existing' && needsLeanDecision && lakePath === '')}
              onClick={() => void startAll()}
            >
              {running
                ? 'Setting everything up…'
                : anythingStarted
                  ? 'Finish the setup'
                  : 'Set everything up'}
            </Button>
            <span className="text-[11px] text-ink-faint">
              {running
                ? 'leave this page open or come back later — it keeps going'
                : 'safe to press again at any time; finished parts are skipped'}
            </span>
          </div>
        </div>
      )}

      {/* ------------------------------------------------ progress */}
      {/* always visible: a user who arrived from the "Claude Code is not
          installed" banner must SEE Claude Code in the list here, not
          only after pressing the button */}
      <div className="mt-4 rounded-lg border border-edge bg-surface p-4">
        <div className="mb-1 text-sm font-medium text-ink">
          {anythingStarted ? 'Progress' : 'What the setup installs'}
        </div>

          <StepRow ok title="Asterism itself" detail={<span className="font-mono">{st.repo}</span>} />

          <StepRow
            ok={st.claude.installed}
            busy={running && !st.claude.installed}
            title="Claude Code"
            detail={
              st.claude.installed
                ? 'installed — the AI that writes the proofs'
                : running
                  ? 'installing…'
                  : 'the AI that writes the proofs — installed for you'
            }
          />

          <StepRow
            ok={st.claude.logged_in}
            busy={false}
            title="Claude login"
            detail={
              st.claude.logged_in
                ? 'logged in — your Claude subscription pays for the proving'
                : st.claude.installed
                  ? 'the one step that needs you'
                  : 'waits for Claude Code'
            }
          >
            {st.claude.installed && !st.claude.logged_in && (
              <div className="mt-1.5">
                <Button variant="primary" onClick={openLogin}>
                  Log in with your browser
                </Button>
                <span className="ml-2 text-[11px] text-ink-faint">
                  a browser tab opens — click Authorize, and you're done
                </span>
              </div>
            )}
          </StepRow>

          <StepRow
            ok={st.git.found}
            busy={running && !st.git.found}
            title="Git"
            detail={
              st.git.found
                ? 'found — the engine records proofs with it'
                : running
                  ? 'installing…'
                  : 'needed to fetch the math library and record proofs'
            }
          />

          <StepRow
            ok={st.lake.found}
            busy={running && st.git.found && !st.lake.found}
            title="Lean theorem prover"
            detail={
              st.lake.found ? (
                <>
                  <span className="font-mono">{st.lake.version}</span>
                  <span className="ml-2 truncate font-mono text-[11px]">{st.lake.path}</span>
                </>
              ) : running ? (
                'installing… (~1 GB)'
              ) : undefined
            }
          />

          <StepRow
            ok={st.mathlib.present}
            busy={running && st.lake.found && !st.mathlib.present}
            title="Math library (Mathlib)"
            detail={
              st.mathlib.present
                ? 'ready — the prebuilt cache is in place'
                : running
                  ? st.lake.found
                    ? 'fetching… (several GB, the long step)'
                    : 'waits for Lean'
                  : st.lake.found
                    ? 'not fetched yet (several GB)'
                    : 'waits for Lean'
            }
          />

          {job.state === 'failed' && (
            <div className="mt-2 text-xs text-warn">
              some steps failed — the log below has the details; press the button above to retry
              just those
            </div>
          )}

          <JobLog job={job} />
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
            this page keeps itself up to date — closing it does not stop the install
          </span>
        )}
      </div>
    </div>
  )
}

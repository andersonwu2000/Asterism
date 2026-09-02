import { useState } from 'react'
import { apiPost, usePoll } from '../lib/api'
import { Link } from '../lib/router'
import { signOut, switchAccount } from '../lib/providerAuth'
import { relTime } from '../lib/format'
import { currentTheme, setTheme } from '../lib/theme'
import type { Theme } from '../lib/theme'
import { Button } from '../components/ui'
import { MachineParameters } from '../components/RunParameters'
import { QuotaMeter } from './EngineRoom'
import { scopedRows } from '../lib/quota'
import { PROVIDER_LABEL, windowLabel } from '../lib/vocab'
import type { Meta, ProviderRow, RunStatus } from '../lib/types'
import type { ShutdownPreview } from '../lib/types'
import { markStopped } from '../lib/shutdown'

/*
 * The gear — the ONE settings page (human_interface_design.md §1.4:
 * "全域、很少動的東西"), shared by the Project picker and every Project.
 *
 * What earns a place here is what you set once for the installation:
 * the accounts the engine spends and what is left of them, the machine
 * parameters (how many agents at once, the warm pool), how this console
 * looks, and how to stop everything. What a RUN does — which model sits
 * in which seat, the time budget — is not here on the owner's ruling:
 * "每次 run 都可能改的東西不藏在設定", so it lives beside Run on the Tasks
 * page.
 */

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-edge bg-surface px-4 py-3">{children}</div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2 text-[11px] tracking-wider text-ink-faint uppercase">
      {children}
    </div>
  )
}

/** VENDOR NAMES, for the one thing a declaration cannot carry: what a
 * person calls this thing. Everything else on the card is measured or
 * declared. */
/** One account, drawn from what the backend DECLARES about itself plus
 * what this machine has of it (`/api/meta` -> providers).
 *
 * There used to be a hand-written component per vendor. Codex made it
 * three (2026-08-14) and the fourth would have wanted a fourth — which
 * is the branch-per-backend `llm/capabilities.py` exists to stop,
 * wearing copy instead of code. Nothing here is vendor-specific any
 * more: the switch/sign-out pair follows `can_login`/`can_logout`,
 * which say what the backend declared about its own sign-in — claude
 * and codex both answer yes (2026-08-26), and the row that reads
 * "claude only" was already wrong the day codex landed.
 *
 * The status word follows `auth_state`, and the tri-state matters:
 * `readable` can say signed in or not; `opaque` cannot say either, so
 * it reports what it CAN see and offers a check; `undeclared` says
 * nothing rather than inventing a verdict.
 */
function Account({ p, onChanged }: { p: ProviderRow; onChanged: () => void }) {
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const seated = p.seats.length > 0
  const label = PROVIDER_LABEL[p.name] ?? p.name
  const run = async (fn: () => Promise<string>) => {
    setBusy(true)
    try {
      setMsg(await fn())
    } catch (e) {
      setMsg(String((e as Error).message))
    } finally {
      setBusy(false)
      onChanged()
    }
  }
  // This panel is about accounts that get SPENT. A backend with no seat
  // spends nothing, so it earns a row only if the reader put it there —
  // installed, by something they ran. That hides the HTTP-only backend
  // (nothing to install, so "installed" is a sentinel rather than a
  // fact about this machine) and any CLI that happens to be on PATH
  // without a seat pointing at it. Choosing one is the Engine page's
  // picker, which offers every declared backend.
  if (!seated && !(p.installed && p.install_method === 'by_command'))
    return null

  // Tri-state, and the third one matters: `readable` says a file
  // COULD state the answer, not that anyone read it. serve reads
  // claude's; for another readable backend the honest value is unknown,
  // and rendering unknown as "not signed in" is a nag that never
  // clears (codex read that way the moment it landed, 2026-08-14).
  const signedIn = p.logged_in === undefined ? null : p.logged_in
  // the api-key flavor: the credential is an env/.env line, presence is
  // the honest local answer, and there is deliberately NO input field —
  // a key typed into a browser form would cross an unauthenticated HTTP
  // layer and land in a second store (owner, 2026-08-22)
  const keyed = p.auth_flow === 'api_key' && Boolean(p.env_key)
  const dot = !p.installed
    ? seated
      ? 'bg-warn'
      : 'bg-ink-faint'
    : keyed
      ? p.key_present
        ? 'bg-ok'
        : 'bg-warn'
      : signedIn === false
        ? 'bg-warn'
        : 'bg-ok'
  const line = !p.installed
    ? seated
      ? `${label} missing — a seat is pointed at it`
      : `${label} not installed`
    : keyed
      ? p.key_present
        ? `${label} — key in place`
        : `${label} has no key`
      : signedIn === true
        ? `${label} signed in${p.subscription ? ` · ${p.subscription} plan` : ''}`
        : signedIn === false
          ? `${label} is not signed in`
          : `${label} installed`

  return (
    <Row>
      <div className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-3">
          <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />
          <span className="text-xs text-ink">{line}</span>
          <span className="ml-auto flex items-center gap-2">
            {/* the account switch, offered to whoever DECLARES one —
                claude was the only vendor with these two buttons until
                codex turned out to make the same move (2026-08-26) */}
            {p.can_login && p.installed && (
              <Button
                variant="outline"
                size="xs"
                disabled={busy}
                title={`opens ${label}'s own browser sign-in — signing in as another account is the switch`}
                onClick={() => void run(() => switchAccount(p.name))}
              >
                Switch account
              </Button>
            )}
            {p.can_logout && p.installed && signedIn !== false && (
              <Button
                variant="outline"
                size="xs"
                disabled={busy}
                title="retires the local session file under a timestamp — reversible by hand, and running agents keep the session they already hold"
                onClick={() => void run(() => signOut(p.name))}
              >
                Sign out
              </Button>
            )}
            {p.can_probe && p.installed && !keyed && (
              /* the honest check where no file states the answer: make
                 the CLI do something the account is needed for. An
                 action, not a poll — agy's costs ~2.5s. */
              <Button
                variant="outline"
                size="xs"
                disabled={busy}
                title="ask this backend whether the account behind it works"
                onClick={() =>
                  void run(async () => {
                    const r = await apiPost<{ ok: boolean; detail: string }>(
                      `/api/providers/${p.name}/check`,
                      {},
                    )
                    return r.detail
                  })
                }
              >
                {busy ? 'Checking…' : 'Check'}
              </Button>
            )}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-faint">
          {seated ? (
            <span>{p.seats.map((x) => x.seat).join(' · ')}</span>
          ) : (
            <span>no seat is pointed at it — nothing here is being spent</span>
          )}
          {p.auth_flow === 'borrowed_session' && (
            <span title="its sign-in lives in another application, not in a file this console can read — so this row reports what it can see, never a guess">
              sign-in lives in its own app
            </span>
          )}
          {keyed &&
            (p.key_present ? (
              <span title="presence only — the key itself is never read, shown, or sent anywhere">
                {p.env_key} found in env / .env
              </span>
            ) : (
              /* the way out, exactly — a warn dot with no reachable
                 action is a nag, not a gate */
              <span className="text-warn">
                add <span className="font-mono">{p.env_key}=…</span> to{' '}
                <span className="font-mono">.env</span> at the workspace root — the engine
                reads it at spawn; the console never asks for the value
              </span>
            ))}
          {p.identity === 'legacy_file' && (
            /* presence is the only detectable signal, and nothing errors
               when the wrong account wins — the run just spends it */
            <span className="text-warn" title={p.identity_path ?? undefined}>
              another credential file is overriding it
            </span>
          )}
          {msg && <span className="text-ink-dim">{msg}</span>}
        </div>
      </div>
    </Row>
  )
}

/** The allowance itself — the same meters the run console shows while
 * you watch it burn, under the account framing instead of the run's.
 * Two sources, and the page says which: claude's is read live from its
 * usage endpoint, codex's is the reading its last agent wrote into its
 * own session log (2026-08-26). */
function Allowance() {
  const { data } = usePoll<RunStatus>('/api/run', 30000)
  const q = data?.quota
  const logged = data?.quota_logged ?? []
  if (!q && logged.length === 0) return null
  return (
    <Row>
      <Label>allowance</Label>
      {logged.length > 0 && q && (
        <div className="mb-1.5 text-[11px] text-ink-dim">{PROVIDER_LABEL.claude}</div>
      )}
      {q && (
      <div className="flex max-w-xl flex-col gap-2">
        {q.five_hour && (
          <QuotaMeter
            label="5-hour window"
            pct={q.five_hour.utilization}
            resetsAt={q.five_hour.resets_at}
          />
        )}
        {q.seven_day && (
          <QuotaMeter
            label="week"
            pct={q.seven_day.utilization}
            resetsAt={q.seven_day.resets_at}
          />
        )}
        {scopedRows(q.scoped).map((s) => (
          <QuotaMeter
            key={s.name}
            label={`${s.name} · week`}
            pct={s.percent}
            resetsAt={s.resets_at}
            quiet={!s.is_active}
            title={
              `${s.name}: a per-model weekly cap your plan reports.` +
              (s.is_active
                ? ' It is the limit binding your spend right now.'
                : ' Another window is binding right now; this one is still counting.')
            }
          />
        ))}
      </div>
      )}
      {logged.map((l) => (
        <div key={l.provider} className={`flex max-w-xl flex-col gap-2 ${q ? 'mt-4' : ''}`}>
          <div className="text-[11px] text-ink-dim">
            {PROVIDER_LABEL[l.provider] ?? l.provider}
            {l.plan && <span className="text-ink-faint"> · {l.plan} plan</span>}
          </div>
          {l.windows.map((w) => (
            <QuotaMeter
              key={w.minutes ?? 'w'}
              label={windowLabel(w.minutes)}
              pct={w.utilization}
              resetsAt={w.resets_at}
            />
          ))}
          <div className="text-[11px] text-ink-faint">
            <span title="this backend has no usage endpoint to ask — it writes its own quota reading into each agent's session log, so the figure moves when an agent finishes a turn and stands still while the engine is idle">
              {l.measured_at
                ? `as its last agent measured it, ${relTime(l.measured_at)}`
                : 'as its last agent measured it'}
            </span>
            {l.reached && (
              <span className="text-warn"> · the window is spent ({l.reached})</span>
            )}
          </div>
        </div>
      ))}
    </Row>
  )
}

/** One control, on the right where a setting's value belongs: a
 * segmented pill whose lit half IS the current end of the scale
 * (owner, 2026-08-07 — two loose buttons read as two things to press,
 * not as one value). */
function Appearance() {
  const [theme, setLocal] = useState<Theme>(() => currentTheme())
  const pick = (t: Theme) => {
    setTheme(t)
    setLocal(t)
  }
  return (
    <Row>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-ink">Appearance</span>
        <span className="text-[11px] text-ink-faint">
          one achromatic language, two ends of its lightness scale
        </span>
        <span className="ml-auto flex overflow-hidden rounded-lg border border-edge">
          {(['dark', 'light'] as const).map((t) => (
            <button
              key={t}
              className={`cursor-pointer px-2.5 py-1 text-xs transition-colors ${
                theme === t
                  ? 'bg-surface-3 text-ink'
                  : 'text-ink-faint hover:text-ink-dim'
              }`}
              onClick={() => pick(t)}
              aria-pressed={theme === t}
            >
              {t}
            </button>
          ))}
        </span>
      </div>
    </Row>
  )
}

/** Quit the whole installation. Three processes, and the reader would
 * only ever guess at the third: the Lean gateway is spawned to OUTLIVE
 * the engine (warming Mathlib costs minutes, so a daemon restart must
 * not pay for it again) and nothing in the product ever ends it —
 * closing the browser leaves it resident. So the card NAMES what is
 * running before it offers to stop it. */
function ShutDown() {
  const { data } = usePoll<ShutdownPreview>('/api/shutdown/preview', 5000)
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  if (!data) return null
  const engine = data.daemon.running
  const gw = data.gateway.phase !== null
  const running = [
    engine
      ? `the engine${data.daemon.scope ? ` on ${data.daemon.scope}` : ''}` +
        (data.daemon.in_flight ? ` — ${data.daemon.in_flight} agent${data.daemon.in_flight === 1 ? '' : 's'} in flight` : '')
      : null,
    gw ? `the Lean gateway (${data.gateway.phase})` : null,
    'this console',
  ].filter(Boolean) as string[]

  const quit = async (force: boolean) => {
    setBusy(true)
    setErr(null)
    try {
      await apiPost('/api/shutdown', { force })
      // the server is going; tell the app before its polls start failing
      markStopped()
    } catch (e) {
      setErr(String((e as Error).message))
      setArmed(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Row>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-ink">Shut down</span>
          <span className="text-[11px] text-ink-faint">
            stops everything and frees the port
          </span>
          <span className="ml-auto">
            {!armed ? (
              <Button variant="outline" size="xs" onClick={() => setArmed(true)}>
                Quit Asterism
              </Button>
            ) : (
              /* two-step, in place: the second click NAMES what happens,
                 and it is a different sentence when a run is live */
              <span className="flex items-center gap-2">
                <Button
                  variant={engine ? 'danger' : 'primary'}
                  size="xs"
                  disabled={busy}
                  onClick={() => void quit(engine)}
                >
                  {busy
                    ? 'Stopping…'
                    : engine
                      ? `Confirm — abandon ${data.daemon.in_flight || 'the'} in-flight agent${data.daemon.in_flight === 1 ? '' : 's'}`
                      : 'Confirm — stop everything'}
                </Button>
                <button
                  className="cursor-pointer text-[11px] text-ink-faint hover:text-ink"
                  onClick={() => setArmed(false)}
                >
                  cancel
                </button>
              </span>
            )}
          </span>
        </div>
        <div className="text-[11px] text-ink-faint">
          running now: {running.join(' · ')}
        </div>
        {engine && armed && (
          <div className="text-[11px] text-warn">
            The engine drains when you stop a run from the Engine page; quitting
            here does not wait for it. Stop the run first to lose nothing.
          </div>
        )}
        {err && <div className="text-[11px] text-danger">{err}</div>}
      </div>
    </Row>
  )
}

/** The installation's own numbers: how many agents may work at once,
 * the warm pool above them, and the RAM the worker economy may use.
 * `dispatch.ram_budget` became writable with the rest (`b00783d4`), so
 * the line that said this page could not change it is gone with it —
 * the control IS the answer now. */
function Machine() {
  return (
    <Row>
      <Label>Machine</Label>
      <MachineParameters />
      <div className="mt-2 text-[11px] text-ink-faint">
        a saved change reaches the engine within about a minute: a running daemon finishes
        its in-flight work and hands off to a fresh one on the new settings.
      </div>
    </Row>
  )
}

export default function Settings() {
  const { data: meta, refresh } = usePoll<Meta>('/api/meta', 5000)
  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-5 flex items-baseline gap-3">
        <Link to="/" className="text-[11px] text-ink-faint transition-colors hover:text-ink">
          ‹ projects
        </Link>
        <h1 className="font-display text-[22px] font-medium text-ink">Settings</h1>
      </div>
      <div className="flex flex-col gap-3">
        {(meta?.providers ?? []).map((p) => (
          <Account key={p.name} p={p} onChanged={refresh} />
        ))}
        <Allowance />
        <Machine />
        <Appearance />
        <ShutDown />
      </div>
    </div>
  )
}

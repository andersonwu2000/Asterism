import { useState } from 'react'
import { usePoll } from '../lib/api'
import { logout, switchAccount } from '../lib/claudeAuth'
import { currentTheme, setTheme } from '../lib/theme'
import type { Theme } from '../lib/theme'
import { QuotaMeter } from './Run'
import { scopedRows } from '../lib/quota'
import type { Meta, RunStatus } from '../lib/types'

/*
 * Settings — everything that is NOT the engine's: the accounts it
 * spends, what is left of them, and how this console looks. The split
 * is by subject (owner, 2026-08-07): model choices and dispatch knobs
 * are the machine's business and stay on the Engine page; your login
 * and your theme are yours, and hunting for them inside the machine
 * room read wrong.
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

/** Claude Code — the account the framework spends by default.
 * Switching mid-run is supported: running agents keep the session
 * they hold, new spawns use the next login, and the meters below flip
 * by themselves. */
function ClaudeAccount({ meta, onChanged }: { meta: Meta; onChanged: () => void }) {
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const c = meta.claude
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
  return (
    <Row>
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`h-2 w-2 rounded-full ${c.logged_in ? 'bg-ok' : 'bg-warn'}`}
          aria-hidden
        />
        <span className="text-xs text-ink">
          {c.logged_in
            ? `Claude Code signed in${c.subscription ? ` · ${c.subscription} plan` : ''}`
            : c.installed
              ? 'Claude Code is not signed in'
              : 'Claude Code is not installed'}
        </span>
        {c.installed && (
          <span className="ml-auto flex items-center gap-2">
            <button
              className="cursor-pointer rounded-lg border border-edge bg-surface-2 px-2.5 py-1 text-xs text-ink transition-colors hover:bg-surface-3 disabled:opacity-50"
              disabled={busy}
              onClick={() => void run(switchAccount)}
              title="open the login window for another account — running agents keep their session; new work uses the account you pick"
            >
              Switch account
            </button>
            {c.logged_in && (
              <button
                className="cursor-pointer rounded-lg border border-edge px-2.5 py-1 text-xs text-ink-dim transition-colors hover:text-ink disabled:opacity-50"
                disabled={busy}
                onClick={() => void run(logout)}
              >
                Sign out
              </button>
            )}
          </span>
        )}
      </div>
      {msg && <div className="mt-2 text-[11px] text-ink-faint">{msg}</div>}
    </Row>
  )
}

/** Antigravity (`agy`) — the subscription path to Gemini models.
 * Deliberately quieter than the Claude row: its credentials do not
 * live in a file this console can read, so there is no "signed in"
 * to claim. What it CAN say is whether the CLI exists and which roles
 * are pointed at it — a role on this provider with no CLI installed
 * is a run that dies at its first spawn. */
function AntigravityAccount({ meta }: { meta: Meta }) {
  const a = meta.antigravity
  if (!a) return null
  const used = a.roles.length > 0
  return (
    <Row>
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`h-2 w-2 rounded-full ${
            a.installed ? 'bg-ok' : used ? 'bg-warn' : 'bg-ink-faint'
          }`}
          aria-hidden
        />
        <span className="text-xs text-ink">
          {a.installed
            ? 'Antigravity CLI installed'
            : used
              ? 'Antigravity CLI missing — a role is pointed at it'
              : 'Antigravity CLI not installed'}
        </span>
        <span
          className="ml-auto text-[11px] text-ink-faint"
          title="its sign-in lives in the Antigravity IDE, not in a file this console can read — so this row reports what it can see, never a guess"
        >
          sign-in lives in the IDE
        </span>
      </div>
      <div className="mt-2 text-[11px] text-ink-faint">
        {used ? (
          <>
            spending it:{' '}
            {a.roles.map((r, i) => (
              <span key={r.role}>
                {i > 0 && ', '}
                <span className="text-ink-dim">{r.role}</span>
                {r.model && <span className="font-mono"> · {r.model}</span>}
              </span>
            ))}
          </>
        ) : (
          'no role is pointed at it — nothing here is being spent'
        )}
      </div>
    </Row>
  )
}

/** The allowance itself, read live from the account's own usage — the
 * same meters the run console shows while you watch it burn. */
function Allowance() {
  const { data } = usePoll<RunStatus>('/api/run', 30000)
  const q = data?.quota
  if (!q) return null
  return (
    <Row>
      <Label>allowance</Label>
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

export default function Settings() {
  const { data: meta, refresh } = usePoll<Meta>('/api/meta', 5000)
  return (
    <div className="mx-auto max-w-4xl px-6 py-6">
      <h1 className="font-display text-[22px] font-medium text-ink">Settings</h1>
      <p className="mt-1 mb-5 text-xs text-ink-faint">
        the accounts the engine spends, what is left of them, and how this console
        looks — the knobs that steer the machine itself live on the Engine page.
      </p>
      <div className="flex flex-col gap-3">
        {meta && <ClaudeAccount meta={meta} onChanged={refresh} />}
        {meta && <AntigravityAccount meta={meta} />}
        <Allowance />
        <Appearance />
      </div>
    </div>
  )
}

import { apiPost } from './api'

/*
 * Account switching — the owner's mid-run quota reset. Just open the
 * backend's own browser sign-in: signing in as another account
 * overwrites the session, so there is NO pre-logout. Cancel the browser
 * login and the current session is untouched (the old flow signed you
 * out first, so a cancelled switch stranded you signed-out). Agents
 * already running keep the session they hold; new spawns use the next
 * login. The meters flip to the new account by themselves.
 *
 * Was `claudeAuth`, one vendor's move, until codex turned out to make
 * exactly the same one (2026-08-26): both open a browser OAuth page
 * that finishes by itself, and both keep the session in a file this
 * console can retire. WHICH argv and WHICH file is the backend's own
 * declaration (`capabilities.login_argv` / `credentials_file`) — the
 * console only needs the provider's name.
 */

export async function switchAccount(provider: string): Promise<string> {
  const r = await apiPost<{ opened: boolean; manual?: string }>(
    `/api/providers/${provider}/login`,
    {},
  )
  return r.opened
    ? 'a browser tab opened — sign in as the account you want; your current session stays until you finish'
    : `run "${r.manual ?? `${provider} login`}" in a terminal to switch accounts`
}

export async function signOut(provider: string): Promise<string> {
  const r = await apiPost<{ logged_out: boolean; detail?: string }>(
    `/api/providers/${provider}/logout`,
    {},
  )
  // the file is renamed with a timestamp, never deleted — say so, so
  // "signed out" never reads as "your credential is gone"
  return r.logged_out
    ? 'signed out — the session file is kept, renamed with a timestamp'
    : (r.detail ?? 'already signed out')
}

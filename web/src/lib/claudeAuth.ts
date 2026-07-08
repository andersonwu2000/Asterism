import { apiPost } from './api'

/*
 * Account switching (owner's mid-run quota reset): just open Claude
 * Code's browser login — signing in as another account overwrites the
 * session, so there is NO pre-logout. Cancel the browser login and the
 * current session is untouched (the old flow logged you out first, so
 * a cancelled switch stranded you signed-out). Agents already running
 * keep the session they hold; new spawns use the next login. The
 * meters (plan windows) flip to the new account by themselves.
 */

export async function switchAccount(): Promise<string> {
  const r = await apiPost<{ opened: boolean; manual?: string }>('/api/claude/login', {})
  return r.opened
    ? 'a browser tab opened — sign in as the account you want; your current session stays until you finish'
    : `run "${r.manual ?? 'claude auth login'}" in a terminal to switch accounts`
}

export async function logout(): Promise<string> {
  const r = await apiPost<{ logged_out: boolean; detail?: string }>('/api/claude/logout', {})
  return r.logged_out ? 'logged out' : (r.detail ?? 'already logged out')
}

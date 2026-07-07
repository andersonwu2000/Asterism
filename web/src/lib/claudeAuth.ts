import { apiPost } from './api'

/*
 * Account switching (owner's mid-run quota reset): log the local
 * session out, then open the official login window. Agents already
 * running keep the session they hold; new spawns use the next login.
 * The meters (plan windows) flip to the new account by themselves.
 */

export async function switchAccount(): Promise<string> {
  await apiPost('/api/claude/logout', {})
  const r = await apiPost<{ opened: boolean; manual?: string }>('/api/claude/login', {})
  return r.opened
    ? 'logged out — finish the new login in the window that opened'
    : `logged out — now run "${r.manual ?? 'claude'}" in a terminal to log in`
}

export async function logout(): Promise<string> {
  const r = await apiPost<{ logged_out: boolean; detail?: string }>('/api/claude/logout', {})
  return r.logged_out ? 'logged out' : (r.detail ?? 'already logged out')
}

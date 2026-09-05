import { providerForModel } from './models'
import type { ChatSessionSummary, ChatTurn, ModelGroup } from './types'

/*
 * The session list's laws (assistant_redesign_2026-09-06.md §2). A
 * Project holds many conversations and one current one; these are the
 * rules that decide what a row says, where the list stands, and what
 * a re-ask or a model pick is allowed to do.
 */

const TITLE_MAX = 60

/** The title a conversation wears until someone renames it: the first
 * line of the first question.
 *
 * A MIRROR of the backend's rule, on purpose — the row must be titled
 * the moment the question is sent, and if the two derivations differ
 * the row renames itself when the reload lands. Empty gives empty: the
 * list says "new conversation" itself rather than storing that phrase
 * as if a person had written it. */
export function deriveTitle(text: string): string {
  const first = (text.split('\n').find((l) => l.trim() !== '') ?? '').replace(/\s+/g, ' ').trim()
  if (first.length <= TITLE_MAX) return first
  return first.slice(0, TITLE_MAX - 1).trimEnd() + '…'
}

/** Newest first. A copy: the array is the poll's, and the render on
 * screen is holding it. */
export function sortSessions(rows: ChatSessionSummary[]): ChatSessionSummary[] {
  return rows
    .slice()
    .sort((a, b) => Date.parse(b.updated_at || '') - Date.parse(a.updated_at || ''))
}

/** Edit & re-ask: the transcript as it will stand when the edited
 * question is sent — turn `n` and everything after it are gone.
 *
 * `null` where the index is not a user turn, which is the same refusal
 * the backend makes (422): an answer cannot be re-asked, and the panel
 * must not offer what the server will reject. */
export function truncateAt(turns: ChatTurn[], n: number): ChatTurn[] | null {
  if (!Number.isInteger(n) || n < 0 || n >= turns.length) return null
  if (turns[n].role !== 'user') return null
  return turns.slice(0, n)
}

/** May this session take this model?
 *
 * A session's handle belongs to ONE CLI, so its provider cannot change
 * once it has turns — the way out is a new conversation, and the panel
 * says exactly that. A model nobody offers is NOT refused here: no
 * group claims it, so "start a new conversation" would not be the way
 * out, and the server's 422 names the real offer (`lib/models`: never
 * invent an owner for a name nothing declares). */
export function canSwitchModel(
  session: ChatSessionSummary | null,
  groups: ModelGroup[],
  picked: string,
): boolean {
  if (session === null || session.turns === 0) return true
  const owner = providerForModel(groups, picked)
  if (owner === null) return true
  return owner === session.provider
}

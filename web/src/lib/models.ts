import type { ModelGroup } from './types'

/*
 * One picker decides two settings.
 *
 * A seat's backend is not an independent choice — it is implied by the
 * model — so the console offers ONE control and writes both keys. Two
 * controls would draw the same fact twice and, worse, let them
 * disagree: `provider: codex` with `claude-sonnet-5` is a run that dies
 * at its first spawn, and nothing before the spawn would have said so
 * (owner, 2026-08-14).
 *
 * That makes "which backend owns this model name" a rule, not a
 * lookup, and rules get pinned.
 */

/** The backend that runs `model`, or null when nothing offers it —
 * an env/yaml override may name anything, and inventing an owner for
 * it would silently move the seat to a backend nobody chose. */
export function providerForModel(
  groups: ModelGroup[],
  model: string,
): string | null {
  for (const g of groups) if (g.models.includes(model)) return g.provider
  return null
}

/** What a pick writes: the model always, and the backend whenever the
 * model names one. Never the backend alone — that is the pairing this
 * control exists to keep. */
export function draftForPick(
  groups: ModelGroup[],
  modelKey: string,
  providerKey: string | null,
  picked: string,
): Record<string, string> {
  const owner = providerForModel(groups, picked)
  const out: Record<string, string> = { [modelKey]: picked }
  if (owner && providerKey) out[providerKey] = owner
  return out
}

/** The groups the Assistant may actually seat.
 *
 * `/api/models/refresh` answers for every backend installed on this
 * machine; `/api/chat/state` answers for the ones that can EXPLAIN. The
 * probe is the better list where the two overlap — it is live — but a
 * provider the state never offered cannot answer a question at all, and
 * offering its models seats a conversation on a spawn that dies (field
 * test, 2026-09-06: the picker showed `codex — list not live`). A seat
 * the probe was silent about keeps its declared list rather than
 * vanishing. */
export function explainerGroups(
  stateGroups: ModelGroup[],
  refreshed: ModelGroup[] | null,
): ModelGroup[] {
  if (refreshed === null) return stateGroups
  const seats = new Set(stateGroups.map((g) => g.provider))
  const live = refreshed.filter((g) => seats.has(g.provider))
  const answered = new Set(live.map((g) => g.provider))
  return [...live, ...stateGroups.filter((g) => !answered.has(g.provider))]
}

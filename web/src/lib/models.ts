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

import type { ConfigSetting, UsageKind } from './types'

/** Per-model price weights, top-model output ≡ 1 unit (inherited from
 * the retired demo watcher, deleted 2026-08-26 — the owner's
 * quota-burn axis: on a subscription, quota is
 * metered roughly by backend cost, so weighted units beat raw token
 * counts). Unknown models assume Sonnet tier — never under-count a
 * release this table hasn't met. */
const PRICE_TIERS: [RegExp, { in: number; cw: number; cr: number; out: number }][] = [
  [/fable|mythos|opus-4-[5-9]/, { in: 0.2, cw: 0.25, cr: 0.02, out: 1.0 }],
  [/opus/, { in: 0.6, cw: 0.75, cr: 0.06, out: 3.0 }],
  [/haiku/, { in: 0.04, cw: 0.05, cr: 0.004, out: 0.2 }],
]
const SONNET_TIER = { in: 0.12, cw: 0.15, cr: 0.012, out: 0.6 }

export function priceWeights(model: string) {
  for (const [re, w] of PRICE_TIERS) if (re.test(model)) return w
  return SONNET_TIER
}

/** kind → its configured model, from the /api/config settings list. */
export function modelForKind(settings: ConfigSetting[] | undefined, kind: string): string {
  return String(settings?.find((s) => s.key === `${kind.toLowerCase()}.model`)?.resolved ?? '')
}

/** Weighted burn units across per-kind usage rows. */
export function weightedBurn(
  kinds: UsageKind[],
  settings: ConfigSetting[] | undefined,
): number {
  return kinds.reduce((a, k) => {
    const w = priceWeights(modelForKind(settings, k.kind))
    return (
      a +
      k.input_tokens * w.in +
      (k.cache_new_tokens ?? 0) * w.cw +
      k.cache_read_tokens * w.cr +
      k.output_tokens * w.out
    )
  }, 0)
}

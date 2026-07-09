# putnam_2025_b6 — strategist plan

**Root** `IsGreatest S (1/4)` (frozen; Ingest gated on root).
(A) membership DONE (`solution_achievable_by_square`).
(B) upper bound `r ≤ 1/4` = `core_quarter_bound` (5246, shelved — reopen after crux tail lands).

## LIVE ROUTE (loose-constant bootstrap — ρ_∞ = log4 FINITE) — UNCHANGED, still sound
Iterate c_k, α_0=1, N₀=2 FIXED. α_{k+1}=rα_k²+1→∞ (quadratic_iterate_unbounded s18219).
Fixed m=5 (>4): c_k·5^{α_k}→∞ ≤ g(5) ⇒ False. Contradiction NEEDS α_k→∞ (NEVER bound α globally).
Bootstrap contradiction is legitimately sound (superpolynomial g violates hineq: g=2^n needs
n ≥ r·2^n, false). The route is NOT the problem — the STEP LEMMA statements were under-hypothesised.

## THIS WAKE — DIAGNOSIS of the 6 tail deaths (root cause found)
The crux tail `g_lower_pow_tail_coupled` (5351) died ×2 at assembly (s22637/s22642); the tail
conjunct killed the crux step ×4 before. `crossover_pow` (5353) is PROVED. The remaining crux is
the ∃C q bundle `second_order_g_lower` (5354, open). ROOT CAUSE: the 2nd-order engine (s18287
chain: incr_bound_from_envelope / ggn_iterate_lower) is LOAD-BEARING on `1 ≤ α`, but the tail /
second_order statements carry only `hα : 1/r ≤ α` and NO `r<1` / `1≤α`. Without `r<1` you cannot
conclude α≥1 (memory: putnam_b6_second_order_engine_needs_alpha_ge_one). In THIS problem α≥1 is
FREE (α_0=1, α_{k+1}=rα²+1≥1 invariant) — it was just never threaded into the brick signatures.

## ACTION (this batch)
- Re-Inject (Forward) `second_order_g_lower_a1` = the ∃C q bundle WITH added `hα1 : 1 ≤ α`.
  Roadmap: q := Q = r²α³+rα+1 (> p=rα²+1 since α≥1/r ⇒ rα²≥α); active region via s18287
  (2nd-order telescope) fed back through telescope_sum_lower; boundary [N₀,2N₀) via hband+hcouple;
  C from the joint boundary+crossover budget — DO NOT pre-pin C (∃-bundle, prover picks).
- ConfirmShelve 5246 (still parked; awaits revived tail chain).
- EmitDirective: thread hα1 everywhere.

## NEXT WAKE
- If `second_order_g_lower_a1` LANDS → Inject (Forward, next batch) `g_lower_pow_tail_coupled` v3
  (also carrying hα1): boundary hcouple + cite crossover_pow (proved) + cite second_order_g_lower_a1,
  le_trans glue. Pinned witness c' = c^(r(1+α))/(2·N₀·(rα²+1)) — keep EXACT (siblings depend).
- Then re-assemble the superlinear step (conjunct 4 = tail; conjuncts 1–3 = superlinear_witness_log/
  upper + band_pointwise_superlinear) and Backward on 5246.
- If `second_order_g_lower_a1` DECLINES even WITH hα1 → Backward-decompose it: (i) active-region
  2nd-order poly-lower via s18287, (ii) boundary patch [N₀,2N₀) via hband+hcouple, (iii) ∃-bundle
  assembly picking C,q. Do NOT retreat to first-order (K₀ wall proven) or drop hcouple.

## 5246 (core_quarter_bound) Backward plan (after crux closes), 3 sub-goals
(i) warm-up: iterate threshold_step_quantitative until α_k≥1/r AND c_k≤(2N₀)^{−α_k} (enter band),
    carrying α_k≥1 invariant;
(ii) bootstrap_chain: iterate the coupled step, induct ρ_k ≤ log(2N₀) (band-preserving);
(iii) fixed_point_contradiction: at m=5, c_k·5^{α_k}→∞ ≤ g(5) via quadratic_iterate_unbounded.

## PROVED INFRASTRUCTURE (cite by L_<slug>, do NOT reconstruct)
quadratic_iterate_unbounded s18219, left_endpoint_sum_rpow_lower s18221, telescope_sum_lower s18252,
ggn_telescope_lower s18286, ggn_second_order_telescope_lower s18287, sum_ggn_rpow_le_g s18266,
crossover_pow (PROVED, takes C,q as inputs — reuse in tail assembly), g_ge_self,
solution_achievable_by_square, threshold_bootstrap s18246, threshold_step_quantitative s18256,
superlinear_witness_log, superlinear_witness_upper, band_pointwise_superlinear.

## DEAD — never reintroduce
Tail brick WITHOUT hcouple (boundary-false large α — killed ×4). Any global α-bound. All
fixed-threshold-M ENVELOPE steps + fixed-M0 sink (s18269) + exponent_fixed_point_exists 5338 +
fixed_threshold_envelope 5311 family + coefficient-1 −log step (5340/5341). Witness /(2p) — always
/(2N₀p). First-order-only tail (K₀ wall proven). Power-mean β-extraction (s22620, died at decomp).

## Footguns
^=Real.rpow. solution=1/4. g:ℕ→ℕ, g(n)≥n strictly increasing. α_0=1, r∈(1/4,1). rα²+1>α always.
N₀=2 FIXED, m=5, ρ_∞=log4. hcouple c≤(2N₀)^{−α} load-bearing for the TAIL, not just step output.
hα1 (1≤α) load-bearing for the 2nd-order engine — thread it or the engine dies.

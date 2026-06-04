-- Decomposition via `Finset.orderEmbOfFin s hcard : Fin m ↪o ℕ`, the strict-
-- monotone enumeration of `s` in increasing order. The inequality
-- `∑ k ∈ Icc 1 m, k ≤ ∑ x ∈ s, x` reduces to a pointwise bound + two reindexing
-- equalities, with `Finset.sum_le_sum` as the closer.
-- (A) `orderemb_succ_le`: `i.val + 1 ≤ orderEmbOfFin s hcard i` for every
--     `i : Fin m`. Uses `hpos` (all elements ≥ 1) + strict monotonicity.
-- (B) `sum_eq_orderemb_sum`: `∑ x ∈ s, x = ∑ i : Fin m, orderEmbOfFin s hcard i`
--     — pure reindexing along the order embedding.
-- (C) `sum_icc_eq_sum_succ`: `∑ k ∈ Icc 1 m, k = ∑ i : Fin m, (i.val + 1)` —
--     pure arithmetic identity in `m`.
-- Combinator: `rw [h_arith, h_sum_eq]; apply Finset.sum_le_sum; exact_mod_cast (h_pointwise i)`.
import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs._strategy_s9628

namespace Problems.Minif2f.imo_1978_p5

def arith_le_distinct_pos_sum := @Problems.Minif2f.imo_1978_p5.s9628

end Problems.Minif2f.imo_1978_p5

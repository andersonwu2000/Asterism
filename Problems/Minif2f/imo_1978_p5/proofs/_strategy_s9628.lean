import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_orderemb_succ_le
import Problems.Minif2f.imo_1978_p5.proofs.L_sum_eq_orderemb_sum
import Problems.Minif2f.imo_1978_p5.proofs.L_sum_icc_eq_sum_succ

namespace Problems.Minif2f.imo_1978_p5

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
theorem s9628 :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    ∀ s : Finset ℕ, s.card = m → (∀ x ∈ s, 1 ≤ x) →
      (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ x ∈ s, (x : ℝ)  := by
  intro n a ha h0 m hm s hcard hpos
  have h_pointwise := orderemb_succ_le n a ha h0 m hm s hcard hpos
  have h_sum_eq := sum_eq_orderemb_sum n a ha h0 m hm s hcard hpos
  have h_arith := sum_icc_eq_sum_succ n a ha h0 m hm s hcard hpos
  rw [h_arith, h_sum_eq]
  apply Finset.sum_le_sum
  intro i _
  exact_mod_cast h_pointwise i

end Problems.Minif2f.imo_1978_p5

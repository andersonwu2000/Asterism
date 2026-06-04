import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs
import Problems.Minif2f.aime_1994_p4.proofs.L_nonneg_floor_logb_two

namespace Problems.Minif2f.aime_1994_p4

-- Subset-monotonicity: Icc 1 313 ⊆ Icc 1 m (since 312 < m) and each
-- floor (logb 2 k) is non-negative for k ≥ 1, so the partial sum is monotone.
theorem s9461 : ∀ (m : ℕ), 312 < m →
    (∑ k ∈ Finset.Icc 1 313, Int.floor (Real.logb 2 (k : ℕ))) ≤
      (∑ k ∈ Finset.Icc 1 m, Int.floor (Real.logb 2 (k : ℕ)))  := by
  intro m hm
  have hsub : Finset.Icc 1 313 ⊆ Finset.Icc 1 m :=
    Finset.Icc_subset_Icc le_rfl (by omega)
  have hnn := nonneg_floor_logb_two
  exact Finset.sum_le_sum_of_subset_of_nonneg hsub
    (fun k hk _ => hnn k (Finset.mem_Icc.mp hk).1)

end Problems.Minif2f.aime_1994_p4

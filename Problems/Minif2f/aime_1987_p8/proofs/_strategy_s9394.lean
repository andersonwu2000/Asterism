import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs.L_bounds_for_97
import Problems.Minif2f.aime_1987_p8.proofs.L_k_eq_97_from_bounds

namespace Problems.Minif2f.aime_1987_p8

-- Split `∃! k, P k` (P = ratio bounds for 112/(112+k)) into witness (k=97) + uniqueness.
-- `bounds_for_97`: pure numeric check that k=97 satisfies both bounds (Builder).
-- `k_eq_97_from_bounds`: any y satisfying both bounds must equal 97 (Backward;
-- clear denominators, get 96 < y < 98 over ℕ, then omega). Combined via the
-- `⟨witness, prop_at_witness, uniqueness⟩` constructor for `ExistsUnique`.
theorem s9394 :
    ∃! k : ℕ, (8 : ℝ) / 15 < (112 : ℝ) / (112 + k)
      ∧ (112 : ℝ) / (112 + k) < 7 / 13  := by
  have h_witness := bounds_for_97
  have h_unique := k_eq_97_from_bounds
  exact ⟨97, h_witness, fun y hy => h_unique y hy⟩

end Problems.Minif2f.aime_1987_p8

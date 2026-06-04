import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs.L_unique_k_for_112

namespace Problems.Minif2f.aime_1987_p8

-- Set membership unfolds to `0 < 112 ∧ ∃! k, …`. The positivity conjunct is `decide`;
-- delegate the unique-existence claim to `unique_k_for_112` (the analytical core: bounds
-- give 96 < k < 98, so k = 97 is the unique witness).
theorem s759 :
    (112 : ℕ) ∈ { n : ℕ | 0 < n ∧
      ∃! k : ℕ, (8 : ℝ) / 15 < n / (n + k) ∧ (n : ℝ) / (n + k) < 7 / 13 } := by
  have h_unique := unique_k_for_112
  exact ⟨by decide, h_unique⟩

end Problems.Minif2f.aime_1987_p8

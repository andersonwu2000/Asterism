import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_real_root_ge_two_exists

namespace Problems.Minif2f.amc12b_2021_p21

-- Decomposition: reduce to a pure-existence statement of a real root ≥ 2 of the
-- defining equation; then membership in S follows from the biconditional h₀.
theorem s9637 : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), ∃ c ∈ S, (2 : ℝ) ≤ c  := by
  intro S h₀
  have h_pure := real_root_ge_two_exists S h₀
  obtain ⟨c, hc_pos, hc_ge, hc_eq⟩ := h_pure
  exact ⟨c, (h₀ c).mpr ⟨hc_pos, hc_eq⟩, hc_ge⟩

end Problems.Minif2f.amc12b_2021_p21

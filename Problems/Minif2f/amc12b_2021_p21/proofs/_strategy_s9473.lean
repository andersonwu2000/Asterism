import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_exists_root_ge_two
import Problems.Minif2f.amc12b_2021_p21.proofs.L_sqrt2_in_s

namespace Problems.Minif2f.amc12b_2021_p21

-- Decomposition: pick a := √2 (always in S by reflexivity) and b := c where c ≥ 2
-- is another root of the equation. Sub-goal 1 establishes √2 ∈ S; sub-goal 2 produces
-- c ∈ S with 2 ≤ c. Distinctness follows since √2 < 2 ≤ c, and a + b = √2 + c ≥ 2
-- since √2 ≥ 0 and c ≥ 2.
theorem s9473 : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), ∃ a b : ℝ, a ≠ b ∧ a ∈ S ∧ b ∈ S ∧ (2 : ℝ) ≤ a + b  := by
  intro S h₀
  have h_sqrt2 : Real.sqrt 2 ∈ S := sqrt2_in_s S h₀
  have h_other : ∃ c ∈ S, (2 : ℝ) ≤ c := exists_root_ge_two S h₀
  obtain ⟨c, hc_in_S, hc_ge⟩ := h_other
  have h_sqrt2_lt_two : Real.sqrt 2 < 2 := by
    nlinarith [Real.sq_sqrt (by norm_num : (0:ℝ) ≤ 2), Real.sqrt_nonneg 2]
  have hc_ne_sqrt2 : c ≠ Real.sqrt 2 := by linarith
  have h_sqrt2_nn : 0 ≤ Real.sqrt 2 := Real.sqrt_nonneg 2
  exact ⟨Real.sqrt 2, c, fun h => hc_ne_sqrt2 h.symm, h_sqrt2, hc_in_S, by linarith⟩

end Problems.Minif2f.amc12b_2021_p21

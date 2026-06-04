import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_func_continuous_on
import Problems.Minif2f.amc12b_2021_p21.proofs.L_func_diff_four_nonpos
import Problems.Minif2f.amc12b_2021_p21.proofs.L_func_diff_two_nonneg

namespace Problems.Minif2f.amc12b_2021_p21

-- Decomposition: apply IVT to f(x) = x^(2^√2) - √2^(2^x) on [2,4].
-- f(2) ≥ 0 (since 2^(2^√2) ≥ 4 = √2^4) and f(4) ≤ 0 (since 2·2^√2 ≤ 8).
-- Continuity on [2,4] (positive base) lets IVT yield a root c ∈ [2,4].
theorem s9680 : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), ∃ c : ℝ, 0 < c ∧ (2 : ℝ) ≤ c ∧ c ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ c  := by
  intro _ _
  have h2 := func_diff_two_nonneg
  have h4 := func_diff_four_nonpos
  have hcont := func_continuous_on
  obtain ⟨c, hc_mem, hfc⟩ :=
    intermediate_value_Icc' (by norm_num : (2:ℝ) ≤ 4) hcont (Set.mem_Icc.mpr ⟨h4, h2⟩)
  refine ⟨c, ?_, hc_mem.1, ?_⟩
  · linarith [hc_mem.1]
  · linarith [hfc]

end Problems.Minif2f.amc12b_2021_p21

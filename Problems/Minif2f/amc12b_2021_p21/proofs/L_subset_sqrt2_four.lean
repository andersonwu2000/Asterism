import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- entry_kind: Backward
theorem subset_sqrt2_four : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), S ⊆ ({Real.sqrt 2, 4} : Finset ℝ) := by sorry

end Problems.Minif2f.amc12b_2021_p21

import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- entry_kind: Builder
theorem sqrt2_in_s : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), Real.sqrt 2 ∈ S := by simp_all only [Real.sqrt_pos, Nat.ofNat_pos, and_self, implies_true]

end Problems.Minif2f.amc12b_2021_p21

import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs

namespace Problems.Minif2f.amc12a_2019_p21

-- entry_kind: Builder
theorem sum_inv_pow_sq_zero_mod_four : ∀ (z : ℂ) (_h₀ : z = (1 + Complex.I) / Real.sqrt 2) (_hz4 : z ^ 4 = -1) (_hzne : z ≠ 0), (∑ k ∈ ({4,8,12} : Finset ℕ), 1 / z ^ k ^ 2) = 3 := by grind

end Problems.Minif2f.amc12a_2019_p21

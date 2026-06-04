import Mathlib
import Problems.Minif2f.amc12a_2008_p4.Defs

namespace Problems.Minif2f.amc12a_2008_p4

-- entry_kind: Builder
theorem four_k_telescope_zero :
    (∏ k ∈ Finset.Icc (1 : ℕ) 0, ((4 : ℝ) * k + 4) / (4 * k)) = ((0 : ℕ) : ℝ) + 1 := by norm_num

end Problems.Minif2f.amc12a_2008_p4

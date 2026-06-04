import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- entry_kind: Builder
theorem sum_real_eq_sum_via_nat_cast :
    (∑ j ∈ Finset.range 330, (1 : ℝ) / ((660 + (j : ℝ)) * (1319 - (j : ℝ)))) =
      (∑ j ∈ Finset.range 330,
        (1 : ℝ) / ((((660 + j) * (1319 - j) : ℕ) : ℝ))) := by norm_num

end Problems.Minif2f.imo_1979_p1

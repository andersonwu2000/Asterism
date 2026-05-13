import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- entry_kind: Backward
set_option linter.style.longLine false in
theorem sum_cos_eq_sum_sin_scaled :
    (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos (n * π / 180)) =
      (1 + Real.sqrt 2) * (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)) := by sorry

end Problems.Minif2f.aime_1997_p11

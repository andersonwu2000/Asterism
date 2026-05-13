import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- floor_hundred_one_plus_sqrt_two_2: bound √2 ∈ [1.41, 1.42) via sqrt_le_sqrt/sqrt_lt_sqrt,
-- then close ⌊100·(1+√2)⌋ = 241 with Int.floor_eq_iff + linarith.
theorem floor_hundred_one_plus_sqrt_two_2 : Int.floor (100 * (1 + Real.sqrt 2)) = 241 := by
  have hsqrt_lb : (141 : ℝ) / 100 ≤ Real.sqrt 2 := by
    rw [← Real.sqrt_sq (by norm_num : (0:ℝ) ≤ 141 / 100)]
    apply Real.sqrt_le_sqrt
    norm_num
  have hsqrt_ub : Real.sqrt 2 < (142 : ℝ) / 100 := by
    rw [← Real.sqrt_sq (by norm_num : (0:ℝ) ≤ 142 / 100)]
    apply Real.sqrt_lt_sqrt (by norm_num)
    norm_num
  rw [Int.floor_eq_iff]
  push_cast
  constructor <;> linarith

end Problems.Minif2f.aime_1997_p11

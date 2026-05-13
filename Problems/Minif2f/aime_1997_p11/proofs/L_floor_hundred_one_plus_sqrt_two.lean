import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- floor_hundred_one_plus_sqrt_two: floor(100*(1+√2)) = 241 via rational bounds 1.41 ≤ √2 < 1.42
theorem floor_hundred_one_plus_sqrt_two : Int.floor (100 * (1 + Real.sqrt 2)) = 241 := by
  have hnn : (0:ℝ) ≤ Real.sqrt 2 := Real.sqrt_nonneg 2
  have h_lower : (141:ℝ) / 100 ≤ Real.sqrt 2 := by
    have hsq : Real.sqrt ((141 / 100 : ℝ) ^ 2) = 141 / 100 :=
      Real.sqrt_sq (by norm_num)
    rw [← hsq]
    apply Real.sqrt_le_sqrt
    norm_num
  have h_upper : Real.sqrt 2 < (142:ℝ) / 100 := by
    have hsq : Real.sqrt ((142 / 100 : ℝ) ^ 2) = 142 / 100 :=
      Real.sqrt_sq (by norm_num)
    rw [← hsq]
    apply Real.sqrt_lt_sqrt
    · norm_num
    · norm_num
  rw [Int.floor_eq_iff]
  constructor
  · push_cast
    linarith
  · push_cast
    linarith

end Problems.Minif2f.aime_1997_p11

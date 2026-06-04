import Mathlib

namespace Problems.Minif2f.imo_1993_p5

-- wythoff_floor_pos: Int.le_floor + nlinarith on sqrt 5 bounds proves ⌊(k+1)φ⌋ ≥ 1
-- φ = (1+√5)/2 > 1 and k+1 ≥ 1, so the product ≥ 1; nlinarith closes via sq_sqrt.
theorem wythoff_floor_pos :
    ∀ k : ℕ, (1 : ℤ) ≤ ⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ := by
  intro k
  rw [Int.le_floor]
  push_cast
  have hsq : Real.sqrt 5 * Real.sqrt 5 = 5 := Real.mul_self_sqrt (by norm_num)
  have hpos : 0 < Real.sqrt 5 := Real.sqrt_pos.mpr (by norm_num)
  have hk : (0 : ℝ) ≤ k := Nat.cast_nonneg k
  nlinarith [sq_nonneg (Real.sqrt 5 - 1)]

end Problems.Minif2f.imo_1993_p5

import Mathlib
namespace Problems.Minif2f.aime_1994_p4

-- nonneg_floor_logb_two: logb_nonneg (base=2≥1, arg≥1) + floor_nonneg closes ⌊log₂ k⌋ ≥ 0
theorem nonneg_floor_logb_two :
    ∀ k : ℕ, 1 ≤ k → (0 : ℤ) ≤ Int.floor (Real.logb 2 (k : ℕ)) := by
  intro k hk
  apply Int.floor_nonneg.mpr
  apply Real.logb_nonneg
  · norm_num
  · exact_mod_cast hk

end Problems.Minif2f.aime_1994_p4

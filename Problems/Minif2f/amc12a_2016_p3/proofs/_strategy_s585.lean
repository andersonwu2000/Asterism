import Mathlib
import Problems.Minif2f.amc12a_2016_p3.Defs

namespace Problems.Minif2f.amc12a_2016_p3

-- Direct numeric evaluation: instantiate h₀ at x=3/8, y=-2/5, then resolve the floor.
-- Step 1: 3/8 ÷ (-2/5) = -15/16, and -1 ≤ -15/16 < 0, so Int.floor = -1 via Int.floor_eq_iff.
-- Step 2: 3/8 - (-2/5)·(-1) = 3/8 - 2/5 = -1/40 closed by norm_num.
-- No sub-goals: this is leaf arithmetic on concrete rationals.
theorem s585 : ∀ (f : ℝ → ℝ → ℝ) (h₀ : ∀ x, ∀ (y) (_ : y ≠ 0), f x y = x - y * Int.floor (x / y)), f (3 / 8) (-(2 / 5)) = -(1 / 40)  := by
  intro f h₀
  have hy : -(2/5:ℝ) ≠ 0 := by norm_num
  rw [h₀ (3/8) (-(2/5)) hy]
  have hfloor : Int.floor ((3/8:ℝ) / -(2/5)) = -1 := by
    apply Int.floor_eq_iff.mpr
    refine ⟨?_, ?_⟩
    · norm_num
    · norm_num
  rw [hfloor]
  push_cast
  norm_num

end Problems.Minif2f.amc12a_2016_p3

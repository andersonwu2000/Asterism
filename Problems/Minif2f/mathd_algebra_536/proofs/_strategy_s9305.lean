import Mathlib
import Problems.Minif2f.mathd_algebra_536.Defs

namespace Problems.Minif2f.mathd_algebra_536

open Nat

-- Direct leaf proof: rewrite Real.sqrt 9 = 3, then norm_num closes 6·(8+3)/2 = 33.
-- Numerics: 3! = 6, 2^3 = 8, √9 = 3, so 6·(8+3)/2 = 33.
theorem s9305 : ↑3! * ((2 : ℝ) ^ 3 + Real.sqrt 9) / 2 = (33 : ℝ)  := by
  have h9 : Real.sqrt 9 = 3 := by
    rw [show (9 : ℝ) = 3 ^ 2 by norm_num]
    exact Real.sqrt_sq (by norm_num)
  rw [h9]
  norm_num [Nat.factorial]

end Problems.Minif2f.mathd_algebra_536
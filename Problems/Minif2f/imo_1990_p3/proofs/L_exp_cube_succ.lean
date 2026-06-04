import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- exp_cube_succ: rewrites 3^(k+1)*m = 3^k*m*3 then applies pow_mul
theorem exp_cube_succ : ∀ (k m : ℕ), 2 ^ (3 ^ (k + 1) * m) = (2 ^ (3 ^ k * m))^3 := by
  intro k m
  have h : 3 ^ (k + 1) * m = 3 ^ k * m * 3 := by ring
  rw [h, pow_mul]

end Problems.Minif2f.imo_1990_p3

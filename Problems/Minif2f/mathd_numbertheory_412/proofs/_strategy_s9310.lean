import Mathlib
import Problems.Minif2f.mathd_numbertheory_412.Defs
import Problems.Minif2f.mathd_numbertheory_412.proofs.L_xp1_sq_mod
import Problems.Minif2f.mathd_numbertheory_412.proofs.L_yp5_cube_mod

namespace Problems.Minif2f.mathd_numbertheory_412

-- Split product modulo 19 factor-wise via `Int.mul_emod`.
-- Sub-goals: (x+1)^2 % 19 = 6 from x % 19 = 4 (since 5^2 = 25 ≡ 6),
-- and (y+5)^3 % 19 = 18 from y % 19 = 7 (since 12^3 = 1728 ≡ -1 ≡ 18);
-- then 6 * 18 % 19 = 108 % 19 = 13 by `decide`.
theorem s9310 : ∀ (x y : ℤ) (h₀ : x % 19 = 4) (h₁ : y % 19 = 7), (x + 1) ^ 2 * (y + 5) ^ 3 % 19 = 13  := by
  intro x y h₀ h₁
  have hA : (x + 1) ^ 2 % 19 = 6 := xp1_sq_mod x h₀
  have hB : (y + 5) ^ 3 % 19 = 18 := yp5_cube_mod y h₁
  rw [Int.mul_emod, hA, hB]
  decide

end Problems.Minif2f.mathd_numbertheory_412

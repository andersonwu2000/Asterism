import Mathlib
import Problems.Minif2f.mathd_algebra_547.Defs

namespace Problems.Minif2f.mathd_algebra_547

-- Direct leaf proof: substitute x=5, y=2, then reduce sqrt(5^3 - 2^2) = sqrt(121) = 11.
-- The exponent `2 ^ y` is `Real.rpow` (y : ℝ); we cast 2 to ℕ to apply
-- `Real.rpow_natCast` and reduce to `(2:ℝ)^(2:ℕ) = 4`. The remaining identity
-- `5^3 - 4 = 121 = 11^2` is `norm_num`, closing with `Real.sqrt_sq`.
theorem s684 : ∀ (x y : ℝ) (h₀ : x = 5) (h₁ : y = 2), Real.sqrt (x ^ 3 - 2 ^ y) = 11  := by
  intro x y h₀ h₁
  subst h₀
  subst h₁
  rw [show ((5:ℝ) ^ 3 - 2 ^ (2:ℝ)) = 11^2 by
    rw [show ((2:ℝ) ^ (2:ℝ)) = 4 by
      rw [show (2:ℝ) = ((2:ℕ):ℝ) by norm_num]
      rw [Real.rpow_natCast]
      norm_num]
    norm_num]
  exact Real.sqrt_sq (by norm_num)

end Problems.Minif2f.mathd_algebra_547

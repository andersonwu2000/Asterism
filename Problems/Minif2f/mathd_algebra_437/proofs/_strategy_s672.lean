import Mathlib
import Problems.Minif2f.mathd_algebra_437.Defs
import Problems.Minif2f.mathd_algebra_437.proofs.L_y_lt_x_of_cubes

namespace Problems.Minif2f.mathd_algebra_437

-- Hypotheses are inconsistent: cubing is strictly monotone on ℝ, so x³ = -45 >
-- -101 = y³ forces x > y; but x < ↑n < y forces x < y. Reduce to y_lt_x_of_cubes
-- and close by exfalso + linarith.
theorem s672 : ∀ (x y : ℝ) (n : ℤ) (h₀ : x ^ 3 = -45) (h₁ : y ^ 3 = -101) (h₂ : x < n) (h₃ : ↑n < y), n = -4  := by
  intro x y n h₀ h₁ h₂ h₃
  have h_y_lt_x : y < x := y_lt_x_of_cubes x y h₀ h₁
  exfalso
  linarith

end Problems.Minif2f.mathd_algebra_437

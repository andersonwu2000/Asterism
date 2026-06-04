import Mathlib
import Problems.Minif2f.mathd_algebra_206.Defs
import Problems.Minif2f.mathd_algebra_206.proofs.L_b_ne_zero_from_first_eq
import Problems.Minif2f.mathd_algebra_206.proofs.L_factor_quadratic_solve

namespace Problems.Minif2f.mathd_algebra_206

-- Factor h₃ = b·(a+b+1) = 0 via the quadratic-in-b form; reduce to two leaves.
-- `b_ne_zero_from_first_eq` rules out the b=0 branch using h₁ and h₂
-- (b=0 ⇒ 6a²=0 ⇒ a=0 ⇒ 2a=b, contradicting h₁). `factor_quadratic_solve`
-- divides h₃ by the non-zero b to recover a+b=-1. Both sub-lemmas are
-- pure ℝ-arithmetic and have strictly smaller hypothesis sets.
theorem s9437 : ∀ (a b : ℝ), 2*a ≠ b → (2*a)^2 + a*(2*a) + b = 0 → b^2 + a*b + b = 0 → a + b = -1  := by
  intro a b h₁ h₂ h₃
  have h_b_ne_zero := b_ne_zero_from_first_eq a b h₁ h₂
  exact factor_quadratic_solve a b h_b_ne_zero h₃

end Problems.Minif2f.mathd_algebra_206

import Mathlib
import Problems.Minif2f.mathd_algebra_206.Defs
import Problems.Minif2f.mathd_algebra_206.proofs.L_algebraic_form

namespace Problems.Minif2f.mathd_algebra_206

-- Eliminate f via h₀, reducing to pure algebra on a, b.
-- After `rw [h₀] at h₂ h₃`, h₂/h₃ become polynomial equations
-- (2a)^2 + a*(2a) + b = 0 and b^2 + a*b + b = 0. The single
-- sub-goal `algebraic_form` deduces a + b = -1 from these two
-- equations together with h₁ : 2*a ≠ b (pure ℝ-arithmetic case
-- split: h₃ factors as b*(a+b+1)=0; the b=0 branch contradicts h₁
-- via h₂; the a+b+1=0 branch closes the goal).
theorem s9301 : ∀ (a b : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = x ^ 2 + a * x + b) (h₁ : 2 * a ≠ b) (h₂ : f (2 * a) = 0) (h₃ : f b = 0), a + b = -1  := by
  intro a b f h₀ h₁ h₂ h₃
  rw [h₀] at h₂ h₃
  exact algebraic_form a b h₁ h₂ h₃

end Problems.Minif2f.mathd_algebra_206

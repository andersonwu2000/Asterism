import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs
import Problems.Minif2f.aime_1996_p5.proofs.L_t_eq_23
import Problems.Minif2f.aime_1996_p5.proofs.L_vieta_f

namespace Problems.Minif2f.aime_1996_p5

-- Decompose into (1) Vieta's formulas for f from its three distinct roots a,b,c,
-- and (2) computing t = 23 from those Vieta sums plus the g-hypotheses.
theorem s545 : ∀ (a b c r s t : ℝ) (f g : ℝ → ℝ) (h₀ : ∀ x, f x = x ^ 3 + 3 * x ^ 2 + 4 * x - 11) (h₁ : ∀ x, g x = x ^ 3 + r * x ^ 2 + s * x + t) (h₂ : f a = 0) (h₃ : f b = 0) (h₄ : f c = 0) (h₅ : g (a + b) = 0) (h₆ : g (b + c) = 0) (h₇ : g (c + a) = 0) (h₈ : List.Pairwise (· ≠ ·) [a, b, c]), t = 23  := by
  intro a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  have h_vieta := vieta_f a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  exact t_eq_23 a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h_vieta.1 h_vieta.2.1 h_vieta.2.2

end Problems.Minif2f.aime_1996_p5

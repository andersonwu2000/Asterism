import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs
import Problems.Minif2f.aime_1996_p5.proofs.L_vieta_pair
import Problems.Minif2f.aime_1996_p5.proofs.L_vieta_prod
import Problems.Minif2f.aime_1996_p5.proofs.L_vieta_sum

namespace Problems.Minif2f.aime_1996_p5

-- Split the conjunction into the three Vieta identities for the monic cubic f.
-- (1) `vieta_sum`: a+b+c = -3 (coefficient of x²).
-- (2) `vieta_pair`: ab+bc+ca = 4 (coefficient of x).
-- (3) `vieta_prod`: abc = 11 (constant term, negated).
-- Each sub-goal is strictly simpler (one equation, not a 3-conjunction) and
-- shares the full parent hypothesis bundle; combinator is `⟨_,_,_⟩`.
theorem s9387 : ∀ (a b c r s t : ℝ) (f g : ℝ → ℝ)
    (h₀ : ∀ x, f x = x ^ 3 + 3 * x ^ 2 + 4 * x - 11)
    (h₁ : ∀ x, g x = x ^ 3 + r * x ^ 2 + s * x + t)
    (h₂ : f a = 0) (h₃ : f b = 0) (h₄ : f c = 0)
    (h₅ : g (a + b) = 0) (h₆ : g (b + c) = 0) (h₇ : g (c + a) = 0)
    (h₈ : List.Pairwise (· ≠ ·) [a, b, c]),
    a + b + c = -3 ∧ a*b + b*c + c*a = 4 ∧ a*b*c = 11  := by
  intro a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  have h_sum := vieta_sum a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  have h_pair := vieta_pair a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  have h_prod := vieta_prod a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈
  exact ⟨h_sum, h_pair, h_prod⟩

end Problems.Minif2f.aime_1996_p5

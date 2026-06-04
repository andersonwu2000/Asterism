import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs
import Problems.Minif2f.aime_1996_p5.proofs.L_ring_neg_prod_pair_sums_23
import Problems.Minif2f.aime_1996_p5.proofs.L_vieta_t_eq_neg_prod

namespace Problems.Minif2f.aime_1996_p5

-- Vieta on g: distinct roots a+b, b+c, c+a give t = -(a+b)(b+c)(c+a);
-- then ring identity -(a+b)(b+c)(c+a) = -(a+b+c)(ab+bc+ca) + abc = 23.
theorem s773 : ∀ (a b c r s t : ℝ) (f g : ℝ → ℝ)
    (h₀ : ∀ x, f x = x ^ 3 + 3 * x ^ 2 + 4 * x - 11)
    (h₁ : ∀ x, g x = x ^ 3 + r * x ^ 2 + s * x + t)
    (h₂ : f a = 0) (h₃ : f b = 0) (h₄ : f c = 0)
    (h₅ : g (a + b) = 0) (h₆ : g (b + c) = 0) (h₇ : g (c + a) = 0)
    (h₈ : List.Pairwise (· ≠ ·) [a, b, c])
    (hsum : a + b + c = -3) (hpair : a*b + b*c + c*a = 4) (hprod : a*b*c = 11),
    t = 23  := by
  intro a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ hsum hpair hprod
  have h_vieta := vieta_t_eq_neg_prod a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ hsum hpair hprod
  have h_ring := ring_neg_prod_pair_sums_23 a b c r s t f g h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ hsum hpair hprod
  linarith

end Problems.Minif2f.aime_1996_p5

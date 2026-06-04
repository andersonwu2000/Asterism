import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs

namespace Problems.Minif2f.aime_1996_p5

-- Direct nlinarith closure: Vieta on g for distinct roots a+b, b+c, c+a.
-- Rewriting h₅,h₆,h₇ via h₁ turns the three g-evaluations into the cubic
-- equations whose Vieta combination yields t = -((a+b)(b+c)(c+a)). Distinctness
-- of a+b, b+c, c+a is derived from h₈ (pairwise a≠b, b≠c, a≠c) and serves as
-- nlinarith hint guards (sq_nonneg of pairwise differences encode them).
theorem s9397 : ∀ (a b c r s t : ℝ) (f g : ℝ → ℝ)
    (h₀ : ∀ x, f x = x ^ 3 + 3 * x ^ 2 + 4 * x - 11)
    (h₁ : ∀ x, g x = x ^ 3 + r * x ^ 2 + s * x + t)
    (h₂ : f a = 0) (h₃ : f b = 0) (h₄ : f c = 0)
    (h₅ : g (a + b) = 0) (h₆ : g (b + c) = 0) (h₇ : g (c + a) = 0)
    (h₈ : List.Pairwise (· ≠ ·) [a, b, c])
    (hsum : a + b + c = -3) (hpair : a*b + b*c + c*a = 4) (hprod : a*b*c = 11),
    t = -((a+b)*(b+c)*(c+a))  := by
  intro a b c r s t f g _h₀ h₁ _h₂ _h₃ _h₄ h₅ h₆ h₇ h₈ _hsum _hpair _hprod
  rw [h₁] at h₅ h₆ h₇
  simp [List.pairwise_cons] at h₈
  obtain ⟨⟨hab, hac⟩, hbc⟩ := h₈
  have hpq : a + b ≠ b + c := fun h => hac (by linarith)
  have hqw : b + c ≠ c + a := fun h => hab (by linarith)
  have hpw : a + b ≠ c + a := fun h => hbc (by linarith)
  nlinarith [h₅, h₆, h₇, hpq, hqw, hpw, sq_nonneg (a-b),
    sq_nonneg (b-c), sq_nonneg (c-a)]

end Problems.Minif2f.aime_1996_p5

import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs

namespace Problems.Minif2f.aime_1996_p5

-- entry_kind: Builder
theorem ring_neg_prod_pair_sums_23 : ∀ (a b c r s t : ℝ) (f g : ℝ → ℝ)
    (h₀ : ∀ x, f x = x ^ 3 + 3 * x ^ 2 + 4 * x - 11)
    (h₁ : ∀ x, g x = x ^ 3 + r * x ^ 2 + s * x + t)
    (h₂ : f a = 0) (h₃ : f b = 0) (h₄ : f c = 0)
    (h₅ : g (a + b) = 0) (h₆ : g (b + c) = 0) (h₇ : g (c + a) = 0)
    (h₈ : List.Pairwise (· ≠ ·) [a, b, c])
    (hsum : a + b + c = -3) (hpair : a*b + b*c + c*a = 4) (hprod : a*b*c = 11),
    -((a+b)*(b+c)*(c+a)) = 23 := by grind

end Problems.Minif2f.aime_1996_p5

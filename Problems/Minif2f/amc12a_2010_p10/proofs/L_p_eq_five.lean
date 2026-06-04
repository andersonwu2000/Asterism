import Mathlib
import Problems.Minif2f.amc12a_2010_p10.Defs

namespace Problems.Minif2f.amc12a_2010_p10

-- entry_kind: Builder
theorem p_eq_five (p q : ℝ) (a : ℕ → ℝ)
    (h₀ : ∀ n, a (n + 2) - a (n + 1) = a (n + 1) - a n)
    (h₁ : a 1 = p) (h₂ : a 2 = 9)
    (h₃ : a 3 = 3 * p - q) (h₄ : a 4 = 3 * p + q) :
    p = 5 := by grind

end Problems.Minif2f.amc12a_2010_p10

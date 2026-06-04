import Mathlib
import Problems.Minif2f.amc12b_2003_p6.Defs

namespace Problems.Minif2f.amc12b_2003_p6

-- entry_kind: Builder
theorem disj_of_a_sq_eq_four_thirds :
    ∀ (a r : ℝ) (u : ℕ → ℝ) (h₀ : ∀ k, u k = a * r ^ k)
      (h₁ : u 1 = 2) (h₂ : u 3 = 6),
      a ^ 2 = 4 / 3 → a = 2 / Real.sqrt 3 ∨ a = -(2 / Real.sqrt 3) := by grind

end Problems.Minif2f.amc12b_2003_p6

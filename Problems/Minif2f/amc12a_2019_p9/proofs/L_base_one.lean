import Mathlib
import Problems.Minif2f.amc12a_2019_p9.Defs

namespace Problems.Minif2f.amc12a_2019_p9

-- entry_kind: Builder
theorem base_one : ∀ (a : ℕ → ℚ) (h₀ : a 1 = 1) (h₁ : a 2 = 3 / 7)
    (h₂ : ∀ n, a (n + 2) = a n * a (n + 1) / (2 * a n - a (n + 1))),
    a 1 = 3 / (4 * ((1:ℕ):ℚ) - 1) := by grind

end Problems.Minif2f.amc12a_2019_p9

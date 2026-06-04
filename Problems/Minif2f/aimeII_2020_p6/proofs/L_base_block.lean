import Mathlib
import Problems.Minif2f.aimeII_2020_p6.Defs

namespace Problems.Minif2f.aimeII_2020_p6

-- entry_kind: Builder
theorem base_block : ∀ (t : ℕ → ℚ) (_h₀ : t 1 = 20) (_h₁ : t 2 = 21)
    (_h₂ : ∀ n ≥ 3, t n = (5 * t (n - 1) + 1) / (25 * t (n - 2))),
    t (5 * 0 + 1) = 20 ∧ t (5 * 0 + 2) = 21 ∧
    t (5 * 0 + 3) = 53 / 250 ∧ t (5 * 0 + 4) = 103 / 26250 ∧
    t (5 * 0 + 5) = 101 / 525 := by grind

end Problems.Minif2f.aimeII_2020_p6

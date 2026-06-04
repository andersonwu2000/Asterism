import Mathlib
import Problems.Minif2f.aimeII_2020_p6.Defs

namespace Problems.Minif2f.aimeII_2020_p6

-- Direct closure: introduce binders, destructure the block hypothesis, let `grind`
-- chain the 5 recurrence steps (t(5k+6..5k+10)) using h₂ + the 5 input equalities.
theorem s9638 : ∀ (t : ℕ → ℚ) (_h₀ : t 1 = 20) (_h₁ : t 2 = 21)
    (_h₂ : ∀ n ≥ 3, t n = (5 * t (n - 1) + 1) / (25 * t (n - 2))),
    ∀ k : ℕ,
      (t (5 * k + 1) = 20 ∧ t (5 * k + 2) = 21 ∧
       t (5 * k + 3) = 53 / 250 ∧ t (5 * k + 4) = 103 / 26250 ∧
       t (5 * k + 5) = 101 / 525) →
      (t (5 * (k + 1) + 1) = 20 ∧ t (5 * (k + 1) + 2) = 21 ∧
       t (5 * (k + 1) + 3) = 53 / 250 ∧ t (5 * (k + 1) + 4) = 103 / 26250 ∧
       t (5 * (k + 1) + 5) = 101 / 525)  := by
  intro t h₀ h₁ h₂ k ⟨hk1, hk2, hk3, hk4, hk5⟩
  grind

end Problems.Minif2f.aimeII_2020_p6

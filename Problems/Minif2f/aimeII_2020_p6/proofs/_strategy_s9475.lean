import Mathlib
import Problems.Minif2f.aimeII_2020_p6.Defs
import Problems.Minif2f.aimeII_2020_p6.proofs.L_base_block
import Problems.Minif2f.aimeII_2020_p6.proofs.L_step_block

namespace Problems.Minif2f.aimeII_2020_p6

-- Induct on k. Base case k=0 is a concrete recurrence chain unfolding
-- t 3, t 4, t 5 from h₀, h₁ via h₂; step uses the recurrence at indices
-- 5k+6 and 5k+7 (depending on t(5k+4), t(5k+5)) which collapse to 20, 21,
-- after which 5k+8, 5k+9, 5k+10 follow mechanically — so step is a fixed
-- 5-link computation independent of k.
theorem s9475 : ∀ (t : ℕ → ℚ) (_h₀ : t 1 = 20) (_h₁ : t 2 = 21)
    (_h₂ : ∀ n ≥ 3, t n = (5 * t (n - 1) + 1) / (25 * t (n - 2))),
    ∀ k : ℕ,
      t (5 * k + 1) = 20 ∧ t (5 * k + 2) = 21 ∧
      t (5 * k + 3) = 53 / 250 ∧ t (5 * k + 4) = 103 / 26250 ∧
      t (5 * k + 5) = 101 / 525  := by
  intro t h₀ h₁ h₂
  have h_base := base_block t h₀ h₁ h₂
  have h_step := step_block t h₀ h₁ h₂
  intro k
  induction k with
  | zero => exact h_base
  | succ k ih => exact h_step k ih

end Problems.Minif2f.aimeII_2020_p6

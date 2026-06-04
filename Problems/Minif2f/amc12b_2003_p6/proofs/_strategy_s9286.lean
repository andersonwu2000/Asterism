import Mathlib
import Problems.Minif2f.amc12b_2003_p6.Defs
import Problems.Minif2f.amc12b_2003_p6.proofs.L_a_eq_pm_two_div_sqrt_three
import Problems.Minif2f.amc12b_2003_p6.proofs.L_u_zero_eq_a

namespace Problems.Minif2f.amc12b_2003_p6

-- Decompose: `u 0 = a` (from `h₀ 0`), then `a = ±2/√3` (from system `a*r=2`, `a*r^3=6`).
-- Combine: rewrite `u 0` to `a` and discharge with the disjunction on `a`.
-- u_zero_eq_a is a one-line `simp`/`ring` from `h₀ 0`; a_eq_pm_two_div_sqrt_three carries
-- the system-solve and is the real arithmetic content of the problem.
theorem s9286 : ∀ (a r : ℝ) (u : ℕ → ℝ) (h₀ : ∀ k, u k = a * r ^ k) (h₁ : u 1 = 2)
    (h₂ : u 3 = 6), u 0 = 2 / Real.sqrt 3 ∨ u 0 = -(2 / Real.sqrt 3) := by
  intro a r u h₀ h₁ h₂
  have hu0 := u_zero_eq_a a r u h₀ h₁ h₂
  have ha  := a_eq_pm_two_div_sqrt_three a r u h₀ h₁ h₂
  rw [hu0]; exact ha

end Problems.Minif2f.amc12b_2003_p6

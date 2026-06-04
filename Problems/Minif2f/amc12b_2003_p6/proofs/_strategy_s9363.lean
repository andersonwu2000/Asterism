import Mathlib
import Problems.Minif2f.amc12b_2003_p6.Defs
import Problems.Minif2f.amc12b_2003_p6.proofs.L_a_sq_eq_four_thirds
import Problems.Minif2f.amc12b_2003_p6.proofs.L_disj_of_a_sq_eq_four_thirds

namespace Problems.Minif2f.amc12b_2003_p6

-- Decompose: square the system: from `a*r=2`, `a*r^3=6` derive `a^2 = 4/3`;
-- then the disjunction follows from `(2/√3)^2 = 4/3` and `x^2 = y^2 → x = ±y`.
-- a_sq_eq_four_thirds is pure polynomial arithmetic; disj_of_a_sq_eq_four_thirds
-- is the sqrt/√3 algebraic step, both strictly simpler than the parent.
theorem s9363 : ∀ (a r : ℝ) (u : ℕ → ℝ) (h₀ : ∀ k, u k = a * r ^ k)
    (h₁ : u 1 = 2) (h₂ : u 3 = 6), a = 2 / Real.sqrt 3 ∨ a = -(2 / Real.sqrt 3)  := by
  intro a r u h₀ h₁ h₂
  have h_sq := a_sq_eq_four_thirds a r u h₀ h₁ h₂
  have h_disj := disj_of_a_sq_eq_four_thirds a r u h₀ h₁ h₂
  exact h_disj h_sq

end Problems.Minif2f.amc12b_2003_p6

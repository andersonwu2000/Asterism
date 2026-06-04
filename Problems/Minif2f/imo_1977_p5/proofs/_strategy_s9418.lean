import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs.L_q_eq_44
import Problems.Minif2f.imo_1977_p5.proofs.L_r_eq_41
import Problems.Minif2f.imo_1977_p5.proofs.L_solutions

namespace Problems.Minif2f.imo_1977_p5

-- Decompose: pin q=44, then r=41, then reduce to a concrete diophantine on a,b.
-- q_eq_44 derives q from the AM-QM bound combined with h₂; r_eq_41 then follows
-- from h₂; solutions handles the residual (a-22)²+(b-22)²=1009 case dispatch.
theorem s9418 : ∀ (a b q r : ℕ) (h₀ : r < a + b) (h₁ : a ^ 2 + b ^ 2 = (a + b) * q + r) (h₂ : q ^ 2 + r = 1977), abs ((a : ℤ) - 22) = 15 ∧ abs ((b : ℤ) - 22) = 28 ∨ abs ((a : ℤ) - 22) = 28 ∧ abs ((b : ℤ) - 22) = 15  := by
  intro a b q r h₀ h₁ h₂
  have h_q_eq_44 := q_eq_44 a b q r h₀ h₁ h₂
  have h_r_eq_41 := r_eq_41 a b q r h₀ h₁ h₂
  subst h_q_eq_44
  subst h_r_eq_41
  exact solutions a b h₀ h₁
end Problems.Minif2f.imo_1977_p5

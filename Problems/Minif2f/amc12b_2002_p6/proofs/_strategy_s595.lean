import Mathlib
import Problems.Minif2f.amc12b_2002_p6.Defs
import Problems.Minif2f.amc12b_2002_p6.proofs.L_a_eq_one
import Problems.Minif2f.amc12b_2002_p6.proofs.L_b_eq_neg_two

namespace Problems.Minif2f.amc12b_2002_p6

-- Split the conjunctive conclusion into independent claims under identical hypotheses.
-- a_eq_one and b_eq_neg_two each match the parent's binder/hypothesis signature;
-- combining via And.intro closes the parent.
theorem s595 : ∀ (a b : ℝ) (h₀ : a ≠ 0 ∧ b ≠ 0) (h₁ : ∀ x, x ^ 2 + a * x + b = (x - a) * (x - b)), a = 1 ∧ b = -2  := by
  intro a b h₀ h₁
  have h_a : a = 1 := a_eq_one a b h₀ h₁
  have h_b : b = -2 := b_eq_neg_two a b h₀ h₁
  exact ⟨h_a, h_b⟩

end Problems.Minif2f.amc12b_2002_p6

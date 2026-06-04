import Mathlib
import Problems.Minif2f.amc12a_2002_p1.Defs
import Problems.Minif2f.amc12a_2002_p1.proofs.L_roots_iff_neg_three_halves_or_five
import Problems.Minif2f.amc12a_2002_p1.proofs.L_sum_eq_seven_halves

namespace Problems.Minif2f.amc12a_2002_p1

-- Split into (a) factorization equivalence f x = 0 ↔ x = -3/2 ∨ x = 5, and
-- (b) the Finset sum over (f ⁻¹' {0}).toFinset given that equivalence.
-- (a) is pure ring algebra: f x = 2*(2x+3)*(x-5), then `mul_eq_zero`.
-- (b) is independent of the polynomial form — only uses (a) to enumerate the
-- two-element preimage and compute -3/2 + 5 = 7/2. Each sub-goal is strictly
-- simpler: (a) drops Fintype + the sum; (b) drops the polynomial definition.
theorem s528 : ∀ (f : ℂ → ℂ) (h₀ : ∀ x, f x = (2 * x + 3) * (x - 4) + (2 * x + 3) * (x - 6)) (h₁ : Fintype (f ⁻¹' {0})), (∑ y ∈ (f ⁻¹' {0}).toFinset, y) = 7 / 2  := by
  intro f h₀ h₁
  have h_iff := roots_iff_neg_three_halves_or_five f h₀
  have h_sum := sum_eq_seven_halves f h₁ h_iff
  exact h_sum

end Problems.Minif2f.amc12a_2002_p1

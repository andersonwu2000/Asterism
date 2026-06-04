import Mathlib
import Problems.Minif2f.algebra_apb4leq8ta4pb4.Defs

namespace Problems.Minif2f.algebra_apb4leq8ta4pb4

-- Direct polynomial inequality (a+b)^4 ≤ 8(a^4+b^4) for positive a,b.
-- Expanded form 7a^4 - 4a^3b - 6a^2b^2 - 4ab^3 + 7b^4 ≥ 0 is SOS-closable.
-- nlinarith with square-nonneg hints discharges it without using h₀.
theorem s553 : ∀ (a b : ℝ) (h₀ : 0 < a ∧ 0 < b), (a + b) ^ 4 ≤ 8 * (a ^ 4 + b ^ 4)  := by
  intro a b _
  nlinarith [sq_nonneg (a - b), sq_nonneg (a + b), sq_nonneg (a^2 - b^2),
    sq_nonneg (a*b), sq_nonneg (a^2 + b^2 - 2*a*b)]

end Problems.Minif2f.algebra_apb4leq8ta4pb4

import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs

namespace Problems.Minif2f.mathd_numbertheory_221

-- prime_sq_lt_1000_in_set: enumerate primes p with p^2 < 1000 via interval_cases;
-- for each non-prime in [2,31] close with absurd, for each prime verify membership with decide
theorem prime_sq_lt_1000_in_set :
    ∀ p : ℕ, p.Prime → p^2 < 1000 →
      p^2 ∈ ({4, 9, 25, 49, 121, 169, 289, 361, 529, 841, 961} : Finset ℕ) := by
  intro p hp hlt
  have h_lb : 2 ≤ p := hp.two_le
  have h_ub : p ≤ 31 := by nlinarith [sq_nonneg p]
  interval_cases p <;> first | exact absurd hp (by decide) | decide

end Problems.Minif2f.mathd_numbertheory_221

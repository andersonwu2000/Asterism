import Mathlib
import Problems.Minif2f.mathd_numbertheory_403.Defs

namespace Problems.Minif2f.mathd_numbertheory_403

-- Direct kernel computation: 198 = 2 · 3² · 11, so its proper divisors are
-- {1,2,3,6,9,11,18,22,33,66,99} summing to 270 — `decide` evaluates the
-- Finset sum on a concrete numeral and discharges the equality.
theorem s726 : (∑ k ∈ Nat.properDivisors 198, k) = 270  := by decide

end Problems.Minif2f.mathd_numbertheory_403

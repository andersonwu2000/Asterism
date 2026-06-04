import Mathlib
import Problems.Minif2f.mathd_numbertheory_461.Defs

namespace Problems.Minif2f.mathd_numbertheory_461

-- Direct decidable evaluation: substitute n by the Finset.card expression,
-- then `decide` reduces both the cardinality (= 4) and `3^4 % 8 = 1`.
theorem s733 : ∀ (n : ℕ) (h₀ : n = Finset.card (Finset.filter (fun x => Nat.gcd x 8 = 1) (Finset.Icc 1 7))), 3 ^ n % 8 = 1  := by
  intro n h₀
  subst h₀
  decide

end Problems.Minif2f.mathd_numbertheory_461

import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_five_ge_three
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_five_le_three

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Split `n.factorization 5 = 3` into the two inequalities and close by le_antisymm.
-- Each direction is strictly simpler: a single Nat.le inequality on the same
-- hypothesis, rather than equality. The two bounds are independent — the upper
-- bound rules out k ≥ 4, the lower bound rules out k ∈ {0,1,2}.
theorem s9778 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 5 = 3  := by
  intro n hn
  have h_le := factorization_five_le_three n hn
  have h_ge := factorization_five_ge_three n hn
  exact Nat.le_antisymm h_le h_ge

end Problems.Minif2f.amc12a_2020_p21

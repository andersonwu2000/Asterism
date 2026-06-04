import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_two_lower_bound
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_two_upper_bound

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Split membership in Finset.Icc 3 8 into the two one-sided bounds:
-- `3 ≤ n.factorization 2` (lower) and `n.factorization 2 ≤ 8` (upper).
-- Each carries the same hypothesis but proves a single ≤ instead of an Icc.
theorem s9782 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 2 ∈ Finset.Icc 3 8  := by
  intro n h
  have h_lower : 3 ≤ n.factorization 2 := factorization_two_lower_bound n h
  have h_upper : n.factorization 2 ≤ 8 := factorization_two_upper_bound n h
  exact Finset.mem_Icc.mpr ⟨h_lower, h_upper⟩

end Problems.Minif2f.amc12a_2020_p21

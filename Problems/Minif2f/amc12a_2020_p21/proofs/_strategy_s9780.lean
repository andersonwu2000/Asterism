import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_seven_factorization_le_one

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Strip the `Finset.Icc 0 1` membership down to its upper-bound half:
-- the lower bound 0 ≤ n.factorization 7 is `Nat.zero_le`, leaving the
-- single arithmetic claim `n.factorization 7 ≤ 1` derivable from the
-- lcm/gcd identity at prime 7 as one Builder leaf.
theorem s9780 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 7 ∈ Finset.Icc 0 1  := by
  intro n h
  have h_seven_factorization_le_one := seven_factorization_le_one n h
  exact Finset.mem_Icc.mpr ⟨Nat.zero_le _, h_seven_factorization_le_one⟩

end Problems.Minif2f.amc12a_2020_p21

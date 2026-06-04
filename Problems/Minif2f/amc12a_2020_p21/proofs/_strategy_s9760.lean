import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_seven_bound
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_three_bound
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_two_bound
open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Split the conjunctive bound goal into three independent prime-specific bounds
-- at 2, 3, 7 respectively. Each sub-goal carries the same hypothesis and is
-- strictly simpler (single Finset.Icc membership instead of triple conjunction).
theorem s9760 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 2 ∈ Finset.Icc 3 8 ∧
      n.factorization 3 ∈ Finset.Icc 1 4 ∧
      n.factorization 7 ∈ Finset.Icc 0 1  := by
  intro n h
  have h2 := factorization_two_bound n h
  have h3 := factorization_three_bound n h
  have h7 := factorization_seven_bound n h
  exact ⟨h2, h3, h7⟩

end Problems.Minif2f.amc12a_2020_p21

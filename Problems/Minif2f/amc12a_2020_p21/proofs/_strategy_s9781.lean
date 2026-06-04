import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_three_ge_one
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_three_le_four

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Split the Finset.Icc 1 4 membership into the two bounds 1 ≤ n.factorization 3
-- and n.factorization 3 ≤ 4, then close via Finset.mem_Icc.mpr.
-- Each bound is strictly simpler: a single Nat.le inequality instead of a
-- Finset.Icc membership conjunction.
theorem s9781 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 3 ∈ Finset.Icc 1 4  := by
  intro n hn
  have h_ge := factorization_three_ge_one n hn
  have h_le := factorization_three_le_four n hn
  exact Finset.mem_Icc.mpr ⟨h_ge, h_le⟩

end Problems.Minif2f.amc12a_2020_p21

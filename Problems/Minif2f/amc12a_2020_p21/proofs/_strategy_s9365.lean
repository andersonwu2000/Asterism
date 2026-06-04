import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_witness_finset_card_48

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: extract an explicit witness Finset T with card = 48 satisfying the
-- same membership predicate; close the parent by Finset.ext (any S with the predicate
-- equals T) plus rewriting S.card to T.card.
-- Sub-goal `witness_finset_card_48` does the arithmetic (n forced to 2^a · 3^b · 5^3 · 7^d
-- with a ∈ [3,8], b ∈ [1,4], d ∈ [0,1], giving 6·4·1·2 = 48); combinator below is mechanical.
theorem s9365 : ∀ (S : Finset ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ 5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n), S.card = 48  := by
  intro S h₀
  obtain ⟨T, hcard, hmem⟩ := witness_finset_card_48
  have hST : S = T := by
    apply Finset.ext; intro n; rw [h₀ n, ← hmem n]
  rw [hST]; exact hcard

end Problems.Minif2f.amc12a_2020_p21

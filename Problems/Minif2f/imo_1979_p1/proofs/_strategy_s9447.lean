import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_denom_prod_coprime_1979
import Problems.Minif2f.imo_1979_p1.proofs.L_denom_prod_pos
import Problems.Minif2f.imo_1979_p1.proofs.L_pair_sum_quotient_exists

namespace Problems.Minif2f.imo_1979_p1

-- Witness d = ∏ j ∈ range 330, (660+j)*(1319-j) (a product of factors all
-- in [660,1319], hence < 1979 prime ⇒ coprime); witness n is the
-- corresponding common-denominator numerator. Sub-goals:
--  (A) denom_prod_pos: that product is positive.
--  (B) denom_prod_coprime_1979: that product is coprime to 1979.
--  (C) pair_sum_quotient_exists: ∃ n with sum = n / product (cast to ℝ).
-- Combinator: obtain n from (C); package ⟨n, D, A, B, hsum⟩.
theorem s9447 :
    ∃ (n d : ℕ), 0 < d ∧ Nat.Coprime d 1979 ∧
      (∑ j ∈ Finset.range 330,
          (1 : ℝ) / ((660 + (j : ℝ)) * (1319 - (j : ℝ)))) =
        (n : ℝ) / (d : ℝ)  := by
  have h_pos : 0 < ∏ j ∈ Finset.range 330, ((660 + j) * (1319 - j)) :=
    denom_prod_pos
  have h_cop : Nat.Coprime (∏ j ∈ Finset.range 330, ((660 + j) * (1319 - j))) 1979 :=
    denom_prod_coprime_1979
  have h_quot : ∃ n : ℕ,
      (∑ j ∈ Finset.range 330,
          (1 : ℝ) / ((660 + (j : ℝ)) * (1319 - (j : ℝ)))) =
        (n : ℝ) / ((∏ j ∈ Finset.range 330, ((660 + j) * (1319 - j)) : ℕ) : ℝ) :=
    pair_sum_quotient_exists
  obtain ⟨n, hsum⟩ := h_quot
  exact ⟨n, _, h_pos, h_cop, hsum⟩

end Problems.Minif2f.imo_1979_p1

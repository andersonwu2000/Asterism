import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_card_le_two
import Problems.Minif2f.amc12b_2021_p21.proofs.L_elem_le_four
import Problems.Minif2f.amc12b_2021_p21.proofs.L_sqrt_two_mem

namespace Problems.Minif2f.amc12b_2021_p21

-- Decompose ∑ < 6 via three structural facts: |S| ≤ 2, every element ≤ 4,
-- and √2 ∈ S. Erasing √2 leaves at most one element bounded by 4, so
-- ∑ ≤ √2 + 4 < 6.
theorem s9614 : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), (∑ k ∈ S, k) < 6  := by
  intro S h
  have h_card : S.card ≤ 2 := card_le_two S h
  have h_max  : ∀ x ∈ S, x ≤ 4 := elem_le_four S h
  have h_sqrt : Real.sqrt 2 ∈ S := sqrt_two_mem S h

  -- Combinator: ∑ k ∈ S, k = √2 + ∑ k ∈ S.erase √2, k ≤ √2 + (S.card - 1)·4 ≤ √2 + 4 < 6.
  have h_sum_eq : ∑ k ∈ S, k = Real.sqrt 2 + ∑ k ∈ S.erase (Real.sqrt 2), k := by
    rw [← Finset.sum_erase_add _ _ h_sqrt]; ring
  have h_card_erase : (S.erase (Real.sqrt 2)).card ≤ 1 := by
    rw [Finset.card_erase_of_mem h_sqrt]; omega
  have h_max' : ∀ x ∈ S.erase (Real.sqrt 2), x ≤ 4 :=
    fun x hx => h_max x (Finset.mem_of_mem_erase hx)
  have h_sum_erase_le : ∑ k ∈ S.erase (Real.sqrt 2), k ≤ ((S.erase (Real.sqrt 2)).card : ℝ) * 4 := by
    calc ∑ k ∈ S.erase (Real.sqrt 2), k
        ≤ ∑ _x ∈ S.erase (Real.sqrt 2), (4 : ℝ) := Finset.sum_le_sum h_max'
      _ = ((S.erase (Real.sqrt 2)).card : ℝ) * 4 := by
          rw [Finset.sum_const, nsmul_eq_mul]
  have h_card_real : ((S.erase (Real.sqrt 2)).card : ℝ) ≤ 1 := by exact_mod_cast h_card_erase
  have h_sqrt_lt : Real.sqrt 2 < 2 := by
    nlinarith [Real.sq_sqrt (by norm_num : (0:ℝ) ≤ 2), Real.sqrt_nonneg 2]
  nlinarith [h_sum_eq, h_sum_erase_le, h_card_real, h_sqrt_lt]


end Problems.Minif2f.amc12b_2021_p21

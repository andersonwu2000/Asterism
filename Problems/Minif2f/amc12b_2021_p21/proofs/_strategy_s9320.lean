import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_subset_sqrt2_four

namespace Problems.Minif2f.amc12b_2021_p21

-- Reduce to: S ⊆ {√2, 4}.  Then ∑ k ∈ S, k ≤ √2 + 4 < 6 by finite-sum arithmetic.
theorem s9320 : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), (∑ k ∈ S, k) < 6  := by
  intro S h₀
  have h_subset : S ⊆ ({Real.sqrt 2, 4} : Finset ℝ) := subset_sqrt2_four S h₀

  have h_sqrt2_lt_2 : Real.sqrt 2 < 2 := by
    have h2 : Real.sqrt 2 < Real.sqrt 4 := by
      apply Real.sqrt_lt_sqrt (by norm_num) (by norm_num)
    have h4 : Real.sqrt 4 = 2 := by
      rw [show (4 : ℝ) = 2^2 by norm_num, Real.sqrt_sq (by norm_num : (2:ℝ) ≥ 0)]
    linarith
  have h_ne : (Real.sqrt 2 : ℝ) ≠ 4 := by
    intro heq
    have h_nn : (0:ℝ) ≤ Real.sqrt 2 := Real.sqrt_nonneg _
    linarith
  have h_sum_eq : ∑ k ∈ ({Real.sqrt 2, 4} : Finset ℝ), k = Real.sqrt 2 + 4 := by
    rw [Finset.sum_pair h_ne]
  have h_nonneg : ∀ i ∈ ({Real.sqrt 2, 4} : Finset ℝ), 0 ≤ i := by
    intro i hi
    rw [Finset.mem_insert, Finset.mem_singleton] at hi
    rcases hi with rfl | rfl
    · exact Real.sqrt_nonneg _
    · norm_num
  calc ∑ k ∈ S, k
      ≤ ∑ k ∈ ({Real.sqrt 2, 4} : Finset ℝ), k :=
          Finset.sum_le_sum_of_subset_of_nonneg h_subset (fun i hi _ => h_nonneg i hi)
    _ = Real.sqrt 2 + 4 := h_sum_eq
    _ < 6 := by linarith

end Problems.Minif2f.amc12b_2021_p21

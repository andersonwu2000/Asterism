import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_two_distinct_solutions_exist

namespace Problems.Minif2f.amc12b_2021_p21

-- Decomposition: produce two distinct positive solutions a, b ∈ S with a + b ≥ 2,
-- then lift to ∑ k ∈ S, k via Finset.sum_le_sum_of_subset_of_nonneg on {a,b} ⊆ S
-- (positivity from h₀ gives the nonneg side condition for elements outside {a,b}).
theorem s9388 : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), (↑2 : ℝ) ≤ ∑ k ∈ S, k  := by
  intro S h₀
  have h_two := two_distinct_solutions_exist S h₀
  obtain ⟨a, b, hne, ha, hb, hab⟩ := h_two
  have hpair : ({a, b} : Finset ℝ) ⊆ S := by
    intro x hx
    rcases Finset.mem_insert.mp hx with rfl | hx2
    · exact ha
    · rw [Finset.mem_singleton] at hx2; exact hx2 ▸ hb
  have hsum_pair : ∑ k ∈ ({a, b} : Finset ℝ), k = a + b := by
    rw [Finset.sum_insert (by simp [Finset.mem_singleton, hne]), Finset.sum_singleton]
  have hnonneg : ∀ k ∈ S, k ∉ ({a, b} : Finset ℝ) → 0 ≤ k := by
    intro k hk _
    exact ((h₀ k).mp hk).1.le
  have hle := Finset.sum_le_sum_of_subset_of_nonneg hpair hnonneg
  rw [hsum_pair] at hle
  linarith

end Problems.Minif2f.amc12b_2021_p21

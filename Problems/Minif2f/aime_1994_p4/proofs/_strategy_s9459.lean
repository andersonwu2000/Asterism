import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs

namespace Problems.Minif2f.aime_1994_p4

-- Direct: Finset.Icc 1 m ⊆ Finset.Icc 1 311 (m < 312) plus per-term
-- nonnegativity of `Int.floor (Real.logb 2 k)` for k ≥ 1 closes via
-- Finset.sum_le_sum_of_subset_of_nonneg.
theorem s9459 : ∀ (m : ℕ), 0 < m → m < 312 →
    (∑ k ∈ Finset.Icc 1 m, Int.floor (Real.logb 2 (k : ℕ))) ≤
    (∑ k ∈ Finset.Icc 1 311, Int.floor (Real.logb 2 (k : ℕ)))  := by
  intro m hm hm312
  apply Finset.sum_le_sum_of_subset_of_nonneg
  · intro k hk
    simp only [Finset.mem_Icc] at hk ⊢
    exact ⟨hk.1, by omega⟩
  · intro k hk _
    simp only [Finset.mem_Icc] at hk
    have hk1 : (1 : ℝ) ≤ (k : ℝ) := by exact_mod_cast hk.1
    have hlog : (0 : ℝ) ≤ Real.logb 2 (k : ℕ) := by
      have : (0 : ℝ) ≤ Real.logb 2 (k : ℝ) :=
        Real.logb_nonneg (by norm_num : (1 : ℝ) < 2) hk1
      simpa using this
    exact_mod_cast Int.floor_nonneg.mpr hlog

end Problems.Minif2f.aime_1994_p4

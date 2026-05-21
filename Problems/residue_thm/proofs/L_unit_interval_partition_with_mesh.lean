import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- unit_interval_partition_with_mesh: uniform partition of [0,1] with mesh < η
-- Uses the Archimedean property to choose n > 1/η, then sets t i = i/n.
theorem unit_interval_partition_with_mesh
    (η : ℝ) (hη : 0 < η) :
    ∃ (n : ℕ) (t : ℕ → ℝ),
      t 0 = 0 ∧ t n = 1 ∧
      (∀ i, i < n → t i ≤ t (i+1)) ∧
      (∀ i, i ≤ n → t i ∈ Set.Icc (0:ℝ) 1) ∧
      (∀ i, i < n → t (i+1) - t i < η) := by
  obtain ⟨N, hN⟩ := exists_nat_gt (1 / η)
  have hN_pos : (0 : ℝ) < N := by
    have : (0 : ℝ) < 1 / η := by positivity
    linarith
  have hN_ne : (N : ℝ) ≠ 0 := ne_of_gt hN_pos
  have hN_nat : N ≠ 0 := Nat.cast_ne_zero.mp hN_ne
  refine ⟨N, fun i => (i : ℝ) / N, ?_, ?_, ?_, ?_, ?_⟩
  · simp
  · field_simp
  · intro i _hi
    apply div_le_div_of_nonneg_right _ (le_of_lt hN_pos)
    · push_cast; linarith [Nat.le_succ i]
  · intro i hi
    constructor
    · positivity
    · rw [div_le_one hN_pos]
      exact_mod_cast hi
  · intro i _hi
    have key : (↑(i + 1) : ℝ) / ↑N - ↑i / ↑N = 1 / ↑N := by push_cast; ring
    rw [key, div_lt_iff₀ hN_pos]
    have h1 := mul_lt_mul_of_pos_right hN hη
    rwa [div_mul_cancel₀ 1 (ne_of_gt hη), mul_comm] at h1

end Problems.residue_thm


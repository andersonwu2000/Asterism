import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- arch_unit_interval_mesh_partition: Archimedean partition of [0,1] with mesh < η,
-- using exists_nat_gt + uniform mesh t i = i/n.
theorem arch_unit_interval_mesh_partition
    (η : ℝ) (hη : 0 < η) :
    ∃ (n : ℕ) (t : ℕ → ℝ),
      t 0 = 0 ∧ t n = 1 ∧
      (∀ i, i < n → t i ≤ t (i+1)) ∧
      (∀ i, i ≤ n → t i ∈ Set.Icc (0:ℝ) 1) ∧
      (∀ i, i < n → t (i+1) - t i < η) := by
  obtain ⟨n, hn⟩ := exists_nat_gt (1 / η)
  have hn_pos : 0 < n := by
    have h1 : (0 : ℝ) < 1 / η := div_pos one_pos hη
    exact_mod_cast lt_trans h1 hn
  refine ⟨n, fun i => (i : ℝ) / n, ?_, ?_, ?_, ?_, ?_⟩
  · simp
  · have : (n : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (Nat.pos_iff_ne_zero.mp hn_pos)
    field_simp
  · intro i _
    simp only []
    push_cast
    apply div_le_div_of_nonneg_right
    · linarith
    · exact (Nat.cast_pos.mpr hn_pos).le
  · intro i hi
    constructor
    · positivity
    · rw [div_le_one (Nat.cast_pos.mpr hn_pos)]
      exact_mod_cast hi
  · intro i _
    have hn_cast : (n : ℝ) > 0 := Nat.cast_pos.mpr hn_pos
    have hmesh : (↑(i + 1) : ℝ) / ↑n - ↑i / ↑n = 1 / ↑n := by push_cast; ring
    rw [hmesh, div_lt_iff₀ hn_cast]
    have hprod : η * (1 / η) = 1 := by field_simp
    have hlt : η * (1 / η) < η * (n : ℝ) := mul_lt_mul_of_pos_left hn hη
    linarith
end Problems.residue_thm

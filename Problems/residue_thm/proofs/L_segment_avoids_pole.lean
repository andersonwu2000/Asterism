import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- segment_avoids_pole: ‖h‖ < dist z a and |t| ≤ 1 imply z + t·h ≠ a on [0,1]
theorem segment_avoids_pole {a : ℂ} (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h : ℂ) (hh : ‖h‖ < dist z a) :
    ∀ t ∈ Set.Icc (0:ℝ) 1, z + (t:ℂ) * h ≠ a := by
  intro t ht heq
  have hlt : ‖(t : ℂ) * h‖ < dist z a :=
    calc ‖(t : ℂ) * h‖ = ‖(t : ℂ)‖ * ‖h‖ := norm_mul _ _
      _ ≤ 1 * ‖h‖ := by
          apply mul_le_mul_of_nonneg_right _ (norm_nonneg _)
          simp only [Complex.norm_real, Real.norm_eq_abs, abs_of_nonneg ht.1]
          exact ht.2
      _ = ‖h‖ := one_mul _
      _ < dist z a := hh
  have heq' : a - z = (t : ℂ) * h := by linear_combination -heq
  have hdist : dist z a = ‖(t : ℂ) * h‖ := by
    rw [dist_comm, dist_eq_norm, ← heq']
  linarith

end Problems.residue_thm
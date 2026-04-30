import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Witness extraction: φ ∉ M yields a finite T₀ ⊆ M for which insert φ T₀ is unsatisfiable.
theorem s9_sub_2 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) (hφ : φ ∉ M)
    : ∃ T₀ : Set (PropForm α), T₀ ⊆ M ∧ T₀.Finite ∧ ¬ Sat (insert φ T₀) := by
  have hnotall := hMax φ hφ
  push_neg at hnotall
  obtain ⟨T, hTsub, hTfin, hTunsat⟩ := hnotall
  by_cases hφT : φ ∈ T
  · refine ⟨T \ {φ}, ?_, hTfin.subset Set.diff_subset, ?_⟩
    · intro x hx
      have hxT : x ∈ T := hx.1
      have hxnφ : x ≠ φ := fun h => hx.2 (Set.mem_singleton_iff.mpr h)
      rcases Set.mem_insert_iff.mp (hTsub hxT) with rfl | hxM
      · exact absurd rfl hxnφ
      · exact hxM
    · rw [Set.insert_diff_singleton, Set.insert_eq_of_mem hφT]
      exact hTunsat
  · exfalso
    apply hTunsat
    apply hFinSat T _ hTfin
    intro x hxT
    rcases Set.mem_insert_iff.mp (hTsub hxT) with rfl | hxM
    · exact absurd hxT hφT
    · exact hxM

end Problems.compactness

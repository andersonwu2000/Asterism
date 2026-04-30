import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s12_s3_main_sub_2_sub_2 : ∀ {α : Type} (M : Set (PropForm α)) (p : PropForm α),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) →
    ∃ T₀ : Set (PropForm α), T₀ ⊆ M ∧ T₀.Finite ∧ ¬Sat (insert p T₀) := by
  intro α M p hfinsat hnotfinsat
  push_neg at hnotfinsat
  obtain ⟨T, hTsub, hTfin, hTnotsat⟩ := hnotfinsat
  by_cases hp : p ∈ T
  · refine ⟨T \ {p}, ?_, ?_, ?_⟩
    · intro x hx
      simp only [Set.mem_diff, Set.mem_singleton_iff] at hx
      obtain ⟨hxT, hxnep⟩ := hx
      have hxins := hTsub hxT
      simp only [Set.mem_insert_iff] at hxins
      exact hxins.resolve_left hxnep
    · exact hTfin.subset Set.diff_subset
    · rw [Set.insert_diff_singleton, Set.insert_eq_of_mem hp]
      exact hTnotsat
  · exfalso
    apply hTnotsat
    apply hfinsat T _ hTfin
    intro x hx
    have hxins := hTsub hx
    simp only [Set.mem_insert_iff] at hxins
    rcases hxins with rfl | hxM
    · exact (hp hx).elim
    · exact hxM

end Problems.compactness

import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s4_sub_2 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) (hφ : φ ∉ M) :
    ∃ F : Set (PropForm α), F ⊆ M ∧ F.Finite ∧ ¬Sat (insert φ F) := by
  have h := hMax φ hφ
  push_neg at h
  obtain ⟨T, hTsub, hTfin, hTunsat⟩ := h
  refine ⟨T \ {φ}, ?_, hTfin.subset Set.diff_subset, ?_⟩
  · intro x hx
    simp only [Set.mem_diff, Set.mem_singleton_iff] at hx
    obtain ⟨hxT, hxnφ⟩ := hx
    have hmem := hTsub hxT
    simp only [Set.mem_insert_iff] at hmem
    exact hmem.resolve_left hxnφ
  · intro ⟨v, hv⟩
    apply hTunsat
    refine ⟨v, fun p hp => ?_⟩
    by_cases hpφ : p = φ
    · subst hpφ
      exact hv φ (Set.mem_insert_iff.mpr (Or.inl rfl))
    · apply hv p
      simp only [Set.mem_insert_iff, Set.mem_diff, Set.mem_singleton_iff]
      exact Or.inr ⟨hp, hpφ⟩

end Problems.compactness

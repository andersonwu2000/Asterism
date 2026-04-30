import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Backward: if φ ∈ M and ψ ∈ M then conj φ ψ ∈ M (maximality + eval structure).
theorem s12_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α) (hφ : φ ∈ M) (hψ : ψ ∈ M) : PropForm.conj φ ψ ∈ M := by
  by_contra hNot
  have hBad := hMax (PropForm.conj φ ψ) hNot
  push_neg at hBad
  obtain ⟨T, hTsub, hTfin, hTnotSat⟩ := hBad
  have hT'sub : insert φ (insert ψ (T \ {PropForm.conj φ ψ})) ⊆ M := by
    intro p hp
    simp only [Set.mem_insert_iff, Set.mem_diff, Set.mem_singleton_iff] at hp
    rcases hp with rfl | rfl | ⟨hpT, hpNe⟩
    · exact hφ
    · exact hψ
    · exact (Set.mem_insert_iff.mp (hTsub hpT)).resolve_left hpNe
  have hT'fin : (insert φ (insert ψ (T \ {PropForm.conj φ ψ}))).Finite :=
    ((hTfin.diff).insert ψ).insert φ
  obtain ⟨v, hv⟩ := hFinSat _ hT'sub hT'fin
  have hφTrue : PropForm.eval v φ = true := hv φ (Set.mem_insert _ _)
  have hψTrue : PropForm.eval v ψ = true :=
    hv ψ (Set.mem_insert_of_mem _ (Set.mem_insert _ _))
  apply hTnotSat
  exact ⟨v, fun p hp => by
    by_cases heq : p = PropForm.conj φ ψ
    · subst heq
      simp only [PropForm.eval, Bool.and_eq_true]
      exact ⟨hφTrue, hψTrue⟩
    · exact hv p (Set.mem_insert_of_mem _ (Set.mem_insert_of_mem _
        (Set.mem_diff_of_mem hp (Set.notMem_singleton_iff.mpr heq))))⟩

end Problems.compactness

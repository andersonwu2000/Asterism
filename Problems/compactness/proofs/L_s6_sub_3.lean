import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s6_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α) : φ ∈ M → ψ ∈ M → PropForm.conj φ ψ ∈ M := by
  intro hφ hψ
  by_contra hNotConj
  have hBad := hMax (PropForm.conj φ ψ) hNotConj
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
    ((hTfin.diff).insert _).insert _
  obtain ⟨v, hv⟩ := hFinSat _ hT'sub hT'fin
  have hPhiTrue : PropForm.eval v φ = true :=
    hv φ (Set.mem_insert _ _)
  have hPsiTrue : PropForm.eval v ψ = true :=
    hv ψ (Set.mem_insert_of_mem _ (Set.mem_insert _ _))
  apply hTnotSat
  exact ⟨v, fun p hp => by
    by_cases heq : p = PropForm.conj φ ψ
    · subst heq
      simp [PropForm.eval, hPhiTrue, hPsiTrue]
    · exact hv p (Set.mem_insert_of_mem _ (Set.mem_insert_of_mem _
        (Set.mem_diff_of_mem hp (Set.notMem_singleton_iff.mpr heq))))⟩

end Problems.compactness

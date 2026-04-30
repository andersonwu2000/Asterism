import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s6_sub_2 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α) : PropForm.conj φ ψ ∈ M → ψ ∈ M := by
  intro hConj
  by_contra hNotPsi
  have hBad := hMax ψ hNotPsi
  push_neg at hBad
  obtain ⟨T, hTsub, hTfin, hTnotSat⟩ := hBad
  have hT'sub : insert (PropForm.conj φ ψ) (T \ {ψ}) ⊆ M := by
    intro p hp
    simp only [Set.mem_insert_iff, Set.mem_diff, Set.mem_singleton_iff] at hp
    rcases hp with rfl | ⟨hpT, hpNe⟩
    · exact hConj
    · exact (Set.mem_insert_iff.mp (hTsub hpT)).resolve_left hpNe
  have hT'fin : (insert (PropForm.conj φ ψ) (T \ {ψ})).Finite :=
    (hTfin.diff).insert _
  obtain ⟨v, hv⟩ := hFinSat _ hT'sub hT'fin
  have hPsiTrue : PropForm.eval v ψ = true := by
    have h := hv (PropForm.conj φ ψ) (Set.mem_insert _ _)
    simp only [PropForm.eval, Bool.and_eq_true] at h
    exact h.2
  apply hTnotSat
  exact ⟨v, fun p hp => by
    by_cases heq : p = ψ
    · rw [heq]; exact hPsiTrue
    · exact hv p (Set.mem_insert_of_mem _ (Set.mem_diff_of_mem hp
        (Set.notMem_singleton_iff.mpr heq)))⟩

end Problems.compactness

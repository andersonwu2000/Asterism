import Mathlib
import Problems.Logic.compactness.Defs
import Problems.Logic.compactness.proofs.L_s116_sub_1
import Problems.Logic.compactness.proofs.L_s116_sub_2

namespace Problems.Logic.compactness

theorem s116 : ∀ {α : Type} (S : Set (PropForm α)),
    (∃ M ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
      ∀ N ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        M ⊆ N → N = M) →
    ∃ M : Set (PropForm α),
      (S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α),
        (S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        M ⊆ N → M = N := by
  intro α S h
  obtain ⟨M, hMP, hMmax⟩ := h
  exact ⟨M, s116_sub_1 S M hMP, s116_sub_2 S M hMmax⟩

end Problems.Logic.compactness

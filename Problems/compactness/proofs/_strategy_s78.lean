import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s78_sub_1
import Problems.compactness.proofs.L_s78_sub_2
import Problems.compactness.proofs.L_s78_sub_3
import Problems.compactness.proofs.L_s78_sub_4

namespace Problems.compactness

theorem s78 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ p : PropForm α, p ∉ M →
        ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := by
  intro α S hS
  have hchain : ∀ (C : Set (Set (PropForm α))),
      C.Nonempty → IsChain (· ⊆ ·) C →
      (∀ X ∈ C, ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T :=
    fun C hCne hCchain hCfinsat => s78_sub_2 C hCne hCchain hCfinsat
  obtain ⟨M, hSM, hMfinsat, hMmax⟩ := s78_sub_3 S hS hchain
  exact ⟨M, hSM, hMfinsat, s78_sub_4 M hMfinsat hMmax⟩

end Problems.compactness

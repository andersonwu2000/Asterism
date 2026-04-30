import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s5_sub_1
import Problems.compactness.proofs.L_s5_sub_2
import Problems.compactness.proofs.L_s5_sub_3

namespace Problems.compactness

theorem s5 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      (∀ φ : PropForm α, φ ∉ M →
        ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T) := by
  obtain ⟨M, hSM, hMfinsat, hMmax⟩ :=
    s5_sub_2 S hS (fun C hchain T hT hfin hne => s5_sub_1 C hchain T hT hfin hne)
  exact ⟨M, hSM, hMfinsat, s5_sub_3 M hMfinsat hMmax⟩

end Problems.compactness

import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s19_s4_main_sub_1_sub_1
import Problems.compactness.proofs.L_s19_s4_main_sub_1_sub_2
import Problems.compactness.proofs.L_s19_s4_main_sub_1_sub_3

namespace Problems.compactness

theorem s19_s4_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M' := by
  intro α S hFinSat
  have hCovering := @s19_s4_main_sub_1_sub_1 α S hFinSat
  apply s19_s4_main_sub_1_sub_3 S hFinSat
  intro c hcSub hChain hNone
  have hBound := s19_s4_main_sub_1_sub_2 S hFinSat hCovering c hcSub hChain hNone
  exact ⟨⋃₀c, hBound, fun z hz => Set.subset_sUnion_of_mem hz⟩

end Problems.compactness

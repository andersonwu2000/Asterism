import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s18_s4_main_sub_1_sub_1
import Problems.compactness.proofs.L_s18_s4_main_sub_1_sub_2
import Problems.compactness.proofs.L_s18_s4_main_sub_1_sub_3

namespace Problems.compactness

theorem s18_s4_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M' := by
  intro α S hFinSat
  have hcover := @s18_s4_main_sub_1_sub_1 α
  have hbound := s18_s4_main_sub_1_sub_2 S hcover
  exact s18_s4_main_sub_1_sub_3 S hFinSat hbound

end Problems.compactness

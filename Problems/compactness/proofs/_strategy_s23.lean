import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s23_s4_main_sub_2_sub_1
import Problems.compactness.proofs.L_s23_s4_main_sub_2_sub_2
import Problems.compactness.proofs.L_s23_s4_main_sub_2_sub_3
import Problems.compactness.proofs.L_s23_s4_main_sub_2_sub_4

namespace Problems.compactness

theorem s23_s4_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ M' : Set (PropForm α), M ⊆ M' →
      (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M') →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  intro α M hfinsat hmax p
  constructor
  · intro hneg
    exact s23_s4_main_sub_2_sub_1 M hfinsat hmax p hneg
  · intro hp_not_in
    obtain ⟨U, hU_sub, hU_fin, hU_refute⟩ :=
      s23_s4_main_sub_2_sub_2 M hfinsat hmax p hp_not_in
    have hext : ∀ T : Set (PropForm α), T ⊆ M ∪ {PropForm.neg p} → T.Finite → Sat T :=
      s23_s4_main_sub_2_sub_3 M hfinsat hmax p U hU_sub hU_fin hU_refute
    exact s23_s4_main_sub_2_sub_4 M hfinsat hmax p hext

end Problems.compactness

import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s8_s3_main_sub_2_sub_1
import Problems.compactness.proofs.L_s8_s3_main_sub_2_sub_2
import Problems.compactness.proofs.L_s8_s3_main_sub_2_sub_3

namespace Problems.compactness

theorem s8_s3_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  intro α M hMfinsat hMmax p
  have hrefut : ∀ q : PropForm α, q ∉ M →
      ∃ F : Set (PropForm α), F ⊆ M ∧ F.Finite ∧ ¬Sat (insert q F) :=
    s8_s3_main_sub_2_sub_2 M hMfinsat hMmax
  constructor
  · intro hneg_in_M
    exact s8_s3_main_sub_2_sub_1 M hMfinsat p hneg_in_M
  · intro hp_not_in_M
    exact s8_s3_main_sub_2_sub_3 M hMfinsat hrefut p hp_not_in_M

end Problems.compactness

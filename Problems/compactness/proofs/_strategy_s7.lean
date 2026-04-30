import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s7_s3_main_sub_3_sub_1
import Problems.compactness.proofs.L_s7_s3_main_sub_3_sub_2
import Problems.compactness.proofs.L_s7_s3_main_sub_3_sub_3

namespace Problems.compactness

theorem s7_s3_main_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) := by
  intro α M hFinsat hNeg p q
  constructor
  · intro hConj
    exact ⟨s7_s3_main_sub_3_sub_1 M hFinsat hNeg p q hConj,
           s7_s3_main_sub_3_sub_2 M hFinsat hNeg p q hConj⟩
  · intro ⟨hp, hq⟩
    exact s7_s3_main_sub_3_sub_3 M hFinsat hNeg p q ⟨hp, hq⟩

end Problems.compactness

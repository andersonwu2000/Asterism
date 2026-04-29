import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s9_s3_main_sub_3_sub_1
import Problems.compactness.proofs.L_s9_s3_main_sub_3_sub_2
import Problems.compactness.proofs.L_s9_s3_main_sub_3_sub_3

namespace Problems.compactness

theorem s9_s3_main_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) := by
  intro α M hfinsat hneg p q
  constructor
  · intro hcpq
    exact ⟨s9_s3_main_sub_3_sub_1 M hfinsat hneg p q hcpq,
           s9_s3_main_sub_3_sub_2 M hfinsat hneg p q hcpq⟩
  · intro ⟨hp, hq⟩
    exact s9_s3_main_sub_3_sub_3 M hfinsat hneg p q hp hq

end Problems.compactness

import Problems.compactness.Defs
import Problems.compactness.proofs.L_s25_s4_main_sub_3_sub_1
import Problems.compactness.proofs.L_s25_s4_main_sub_3_sub_2
import Problems.compactness.proofs.L_s25_s4_main_sub_3_sub_3

namespace Problems.compactness

theorem s25_s4_main_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hNeg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) :
    ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) := by
  intro p q
  constructor
  · intro h
    exact ⟨s25_s4_main_sub_3_sub_1 M hFinSat hNeg p q h,
           s25_s4_main_sub_3_sub_2 M hFinSat hNeg p q h⟩
  · intro ⟨hp, hq⟩
    exact s25_s4_main_sub_3_sub_3 M hFinSat hNeg p q hp hq

end Problems.compactness

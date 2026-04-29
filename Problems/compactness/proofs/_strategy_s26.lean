import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s26_s4_main_sub_3_sub_1
import Problems.compactness.proofs.L_s26_s4_main_sub_3_sub_2
import Problems.compactness.proofs.L_s26_s4_main_sub_3_sub_3

namespace Problems.compactness

theorem s26_s4_main_sub_3 {α : Type} (M : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hneg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M)
    (p q : PropForm α) : PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) := by
  have hfwd_p : PropForm.conj p q ∈ M → p ∈ M :=
    s26_s4_main_sub_3_sub_1 M hfinsat hneg p q
  have hfwd_q : PropForm.conj p q ∈ M → q ∈ M :=
    s26_s4_main_sub_3_sub_2 M hfinsat hneg p q
  have hbwd : p ∈ M → q ∈ M → PropForm.conj p q ∈ M :=
    s26_s4_main_sub_3_sub_3 M hfinsat hneg p q
  constructor
  · intro hconj
    exact ⟨hfwd_p hconj, hfwd_q hconj⟩
  · intro ⟨hp, hq⟩
    exact hbwd hp hq

end Problems.compactness

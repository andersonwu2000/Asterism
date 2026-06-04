import Problems.Logic.compactness.proofs.L_s77_sub_1
import Problems.Logic.compactness.proofs.L_s77_sub_2
import Problems.Logic.compactness.proofs.L_s77_sub_3
import Problems.Logic.compactness.proofs.L_s77_sub_4

namespace Problems.Logic.compactness

theorem s77 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := by
  intro α S hS
  obtain ⟨M, hSM, hMfinsat, hMmax⟩ := s77_sub_1 S hS
  have hneg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M :=
    s77_sub_2 M hMfinsat hMmax
  have hconj : ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) :=
    s77_sub_3 M hMfinsat hneg
  obtain ⟨v, hv⟩ := s77_sub_4 M hneg hconj
  exact ⟨v, fun p hp => hv p (hSM hp)⟩

end Problems.Logic.compactness

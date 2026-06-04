import Problems.Logic.compactness.proofs.L_s81_sub_1
import Problems.Logic.compactness.proofs.L_s81_sub_2
import Problems.Logic.compactness.proofs.L_s81_sub_3

namespace Problems.Logic.compactness

theorem s81 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) := by
  intro α M hMfinsat hneg p q
  constructor
  · intro hpq
    have hleft : p ∈ M := s81_sub_1 M hMfinsat hneg p q hpq
    have hright : q ∈ M := s81_sub_2 M hMfinsat hneg p q hpq
    exact ⟨hleft, hright⟩
  · intro ⟨hp, hq⟩
    exact s81_sub_3 M hMfinsat hneg p q hp hq

end Problems.Logic.compactness

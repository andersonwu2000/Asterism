import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s7

namespace Problems.compactness

theorem s3_main_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) := s7_s3_main_sub_3

end Problems.compactness

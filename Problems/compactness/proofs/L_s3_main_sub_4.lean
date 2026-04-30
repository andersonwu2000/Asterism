import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s15

namespace Problems.compactness

theorem s3_main_sub_4 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    ∃ v : Valuation α, ∀ p : PropForm α, p ∈ M → PropForm.eval v p = true := s15_s3_main_sub_4

end Problems.compactness

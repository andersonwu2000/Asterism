import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s12

namespace Problems.compactness

theorem s3_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := s12_s3_main_sub_2

end Problems.compactness

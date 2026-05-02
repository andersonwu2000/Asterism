import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s79

namespace Problems.compactness

theorem s77_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := s79

end Problems.compactness

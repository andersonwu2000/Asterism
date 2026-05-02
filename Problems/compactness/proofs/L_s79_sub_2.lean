import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s83

namespace Problems.compactness

theorem s79_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, p ∉ M →
      ∃ T : Set (PropForm α), T ⊆ M ∧ T.Finite ∧ ¬Sat (insert p T) := s83

end Problems.compactness

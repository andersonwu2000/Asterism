import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s78

namespace Problems.compactness

theorem s77_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ p : PropForm α, p ∉ M →
        ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := s78

end Problems.compactness

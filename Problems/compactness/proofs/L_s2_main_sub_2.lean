import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- A maximal finitely-satisfiable set is itself satisfiable.
-- Proof core: canonical valuation v*(a) := decide (atom a ∈ M) satisfies every p ∈ M
-- via the Truth Lemma proved by structural induction on PropForm,
-- using finsat + maximality to handle the neg and conj cases.
theorem s2_main_sub_2 {α : Type} (M : Set (PropForm α))
    (hM : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ p : PropForm α, p ∉ M →
              ∃ T : Set (PropForm α), T ⊆ insert p M ∧ T.Finite ∧ ¬Sat T) :
    Sat M := by sorry

end Problems.compactness

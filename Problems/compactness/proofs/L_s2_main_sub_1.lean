import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Zorn extension: every finitely-satisfiable set S has a maximal finitely-satisfiable superset M.
-- Maximality is witnessed by: any formula outside M breaks finite satisfiability when inserted.
theorem s2_main_sub_1 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M
      ∧ (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
      ∧ (∀ p : PropForm α, p ∉ M →
           ∃ T : Set (PropForm α), T ⊆ insert p M ∧ T.Finite ∧ ¬Sat T) := by sorry

end Problems.compactness

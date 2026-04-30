import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Zorn extension: every finitely-satisfiable set S has a maximal finitely-satisfiable superset.
theorem s2_sub_1 {α : Type} (S : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      (∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M') := by
  sorry

end Problems.compactness

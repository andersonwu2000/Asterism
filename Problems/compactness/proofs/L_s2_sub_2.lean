import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- A maximal finitely-satisfiable set is complete: it contains p or neg p for every formula.
theorem s2_sub_2 {α : Type} (M : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hmax : ∀ M' : Set (PropForm α), M ⊆ M' →
      (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M') :
    ∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M := by
  sorry

end Problems.compactness

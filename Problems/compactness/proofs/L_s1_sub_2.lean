import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Negation closure: in a maximal fin-sat set M, neg φ ∈ M iff φ ∉ M.
theorem s1_sub_2 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) : PropForm.neg φ ∈ M ↔ φ ∉ M := by
  sorry

end Problems.compactness

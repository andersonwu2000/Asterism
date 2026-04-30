import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

-- Lindenbaum Extension: every fin-sat set has a maximal fin-sat superset, via Zorn's lemma.
theorem s1_sub_1 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      (∀ φ : PropForm α, φ ∉ M →
        ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T) := by
  sorry

end Problems.compactness

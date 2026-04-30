import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Zorn's lemma applied to F = {N | S ⊆ N ∧ FinSat N}.
Given the chain-bound hypothesis, there exists a maximal fin-sat superset M of S.
Maximality is stated in Zorn's form: any fin-sat N with M ⊆ N satisfies N = M. -/
theorem s10_sub_2 {α : Type}
    (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T)
    (hChainBound : ∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C →
        (∀ N ∈ C, ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      (∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → N = M) := by
  sorry

end Problems.compactness

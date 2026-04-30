import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- The canonical valuation v(a) := (atom a ∈ M) satisfies every formula in M,
-- given completeness and closure under negation and conjunction.
theorem s2_sub_5 {α : Type} (M : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hcomplete : ∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M)
    (hneg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M)
    (hconj : ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) :
    Sat M := by
  sorry

end Problems.compactness

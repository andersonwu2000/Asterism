import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Truth lemma and conclusion: given neg-decisiveness and conj-biconditional for M,
the canonical valuation v a := (atom a ∈ M) satisfies all formulas in M (proved by
structural induction on PropForm), so S ⊆ M implies Sat S. -/
theorem s3_sub_4 {α : Type} (S M : Set (PropForm α))
    (hSM : S ⊆ M)
    (hneg : ∀ p : PropForm α, p ∉ M ↔ PropForm.neg p ∈ M)
    (hconj : ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ p ∈ M ∧ q ∈ M) :
    Sat S := by sorry

end Problems.compactness

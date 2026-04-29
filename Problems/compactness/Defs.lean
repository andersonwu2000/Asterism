import Mathlib

/-!
Problem-level shared definitions for the propositional-compactness
exercise. Lives outside proofs/ so that it is not a sub-goal Node and
can be imported by Root.lean and every sub-goal lean file without
creating an import cycle.
-/

namespace Problems.compactness

/-- Boolean valuation of propositional atoms. -/
def Valuation (α : Type) : Type := α → Bool

/-- Propositional formulas over atom type `α`. Minimal signature
(`atom`, `neg`, `conj`) is complete; `or`, `imp`, etc. can be encoded. -/
inductive PropForm (α : Type) where
  | atom : α → PropForm α
  | neg  : PropForm α → PropForm α
  | conj : PropForm α → PropForm α → PropForm α

/-- Evaluation of a formula under a valuation. -/
def PropForm.eval : Valuation α → PropForm α → Bool
  | v, .atom a    => v a
  | v, .neg p     => !PropForm.eval v p
  | v, .conj p q  => PropForm.eval v p && PropForm.eval v q

/-- A set of formulas is satisfiable iff there is a valuation making
every formula in the set evaluate to `true`. -/
def Sat {α : Type} (S : Set (PropForm α)) : Prop :=
  ∃ v : Valuation α, ∀ p ∈ S, PropForm.eval v p = true

end Problems.compactness

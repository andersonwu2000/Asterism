import Mathlib

namespace Problems.Combinatorics.union_closed

/-- The union-closed sets conjecture (Frankl, 1979): a finite family of
finite sets, closed under pairwise union and containing at least one
nonempty member, has an element that belongs to at least half of the
members. "At least half" is stated multiplication-free:
`F.card ≤ 2 * #{A ∈ F : x ∈ A}`. -/
theorem main : ∀ {α : Type} [DecidableEq α] (F : Finset (Finset α)),
    (∀ A ∈ F, ∀ B ∈ F, A ∪ B ∈ F) →
    (∃ A ∈ F, A.Nonempty) →
    ∃ x : α, F.card ≤ 2 * (F.filter (fun A => x ∈ A)).card := by
  sorry

end Problems.Combinatorics.union_closed

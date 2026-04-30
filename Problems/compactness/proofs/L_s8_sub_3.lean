import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Zorn application: given hS (S is fin-sat) and chain bounds for nonempty
chains in F = {N | S ⊆ N ∧ fin-sat N}, produce a ⊆-maximal element M ∈ F. -/
theorem s8_sub_3 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T)
    (hbound : ∀ C : Set (Set (PropForm α)), C.Nonempty → IsChain (· ⊆ ·) C →
        (∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        ∃ UB : Set (PropForm α),
          (∀ N ∈ C, N ⊆ UB) ∧
          S ⊆ UB ∧
          ∀ T : Set (PropForm α), T ⊆ UB → T.Finite → Sat T) :
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α),
        M ⊆ N → (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by sorry

end Problems.compactness

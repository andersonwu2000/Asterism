import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Maximality condition: a ⊆-maximal element M of F satisfies the s1-style
condition that no φ ∉ M can be inserted while preserving finite satisfiability. -/
theorem s8_sub_4 {α : Type} (S : Set (PropForm α)) (M : Set (PropForm α))
    (hSM : S ⊆ M)
    (hMfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMmax : ∀ N : Set (PropForm α),
        M ⊆ N → (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N) :
    ∀ φ : PropForm α, φ ∉ M →
        ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T := by sorry

end Problems.compactness

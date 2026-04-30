import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- In a complete finitely-satisfiable set: conj p q ∈ M iff p ∈ M and q ∈ M.
theorem s2_sub_4 {α : Type} (M : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hcomplete : ∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M) :
    ∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M) := by
  sorry

end Problems.compactness

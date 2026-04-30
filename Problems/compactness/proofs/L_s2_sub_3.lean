import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- In a complete finitely-satisfiable set: neg p ∈ M iff p ∉ M.
theorem s2_sub_3 {α : Type} (M : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hcomplete : ∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M) :
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  sorry

end Problems.compactness

import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Conjunction closure: in a maximal fin-sat set M, conj φ ψ ∈ M iff φ ∈ M and ψ ∈ M.
theorem s1_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α) : PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M) := by
  sorry

end Problems.compactness

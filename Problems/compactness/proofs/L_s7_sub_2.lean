import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Forward direction (ψ): in a maximal fin-sat set M, conj φ ψ ∈ M implies ψ ∈ M.
theorem s7_sub_2 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α)
    (h : PropForm.conj φ ψ ∈ M) : ψ ∈ M := by
  sorry

end Problems.compactness

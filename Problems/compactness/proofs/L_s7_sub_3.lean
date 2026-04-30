import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Backward direction: in a maximal fin-sat set M, φ ∈ M and ψ ∈ M imply conj φ ψ ∈ M.
theorem s7_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α)
    (hφ : φ ∈ M) (hψ : ψ ∈ M) : PropForm.conj φ ψ ∈ M := by
  sorry

end Problems.compactness

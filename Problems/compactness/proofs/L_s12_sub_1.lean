import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Forward left: if conj φ ψ ∈ M then φ ∈ M (maximality + eval structure).
theorem s12_sub_1 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α) (h : PropForm.conj φ ψ ∈ M) : φ ∈ M := by
  sorry

end Problems.compactness

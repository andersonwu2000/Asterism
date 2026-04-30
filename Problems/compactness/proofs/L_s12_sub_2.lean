import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Forward right: if conj φ ψ ∈ M then ψ ∈ M (maximality + eval structure).
theorem s12_sub_2 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ ψ : PropForm α) (h : PropForm.conj φ ψ ∈ M) : ψ ∈ M := by
  sorry

end Problems.compactness

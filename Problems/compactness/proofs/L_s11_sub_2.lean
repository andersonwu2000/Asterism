import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

theorem s11_sub_2 {α : Type} (M : Set (PropForm α))
    (hNeg  : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M))
    (v : Valuation α)
    (hv : ∀ a : α, v a = true ↔ PropForm.atom a ∈ M) :
    ∀ φ : PropForm α, PropForm.eval v φ = true ↔ φ ∈ M := by
  sorry

end Problems.compactness

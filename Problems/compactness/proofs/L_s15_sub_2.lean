import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

-- Conjunction induction step: given IHs for φ and ψ, the canonical valuation satisfies conj φ ψ ↔ conj φ ψ ∈ M.
theorem s15_sub_2 {α : Type} (v : Valuation α) (M : Set (PropForm α))
    (hNeg  : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M))
    (φ ψ : PropForm α)
    (ihφ : PropForm.eval v φ = true ↔ φ ∈ M)
    (ihψ : PropForm.eval v ψ = true ↔ ψ ∈ M) :
    PropForm.eval v (PropForm.conj φ ψ) = true ↔ PropForm.conj φ ψ ∈ M := by
  simp only [PropForm.eval, Bool.and_eq_true, ihφ, ihψ]
  exact (hConj φ ψ).symm

end Problems.compactness

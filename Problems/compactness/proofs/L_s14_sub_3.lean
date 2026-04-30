import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

-- Conj step of the truth-lemma induction: given IHs for φ and ψ and hConj, the conj case holds.
theorem s14_sub_3 {α : Type} (M : Set (PropForm α))
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M))
    (v : Valuation α) (φ ψ : PropForm α)
    (ihφ : φ ∈ M ↔ PropForm.eval v φ = true)
    (ihψ : ψ ∈ M ↔ PropForm.eval v ψ = true) :
    PropForm.conj φ ψ ∈ M ↔ PropForm.eval v (PropForm.conj φ ψ) = true := by
  rw [hConj]
  simp [PropForm.eval, ihφ, ihψ]

end Problems.compactness

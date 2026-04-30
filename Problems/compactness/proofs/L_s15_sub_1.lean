import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

-- Negation induction step: given the IH for φ, the canonical valuation satisfies neg φ ↔ neg φ ∈ M.
theorem s15_sub_1 {α : Type} (v : Valuation α) (M : Set (PropForm α))
    (hNeg  : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M))
    (φ : PropForm α)
    (ih : PropForm.eval v φ = true ↔ φ ∈ M) :
    PropForm.eval v (PropForm.neg φ) = true ↔ PropForm.neg φ ∈ M := by
  constructor
  · intro h
    simp only [PropForm.eval] at h
    rw [hNeg φ]
    intro hφ
    simp [ih.mpr hφ] at h
  · intro h
    rw [hNeg φ] at h
    simp only [PropForm.eval]
    cases hb : PropForm.eval v φ
    · simp
    · exact absurd (ih.mp hb) h

end Problems.compactness

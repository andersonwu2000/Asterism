import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

-- Full bidirectional truth lemma: the canonical valuation v(a) := decide(atom a ∈ M)
-- satisfies eval v φ = true ↔ φ ∈ M for all φ, proved by structural induction.
theorem s15_sub_3 {α : Type} (M : Set (PropForm α))
    (hNeg  : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M)) :
    ∀ φ : PropForm α,
      PropForm.eval (fun a => decide (PropForm.atom a ∈ M)) φ = true ↔ φ ∈ M := by
  intro φ
  induction φ with
  | atom a =>
    simp [PropForm.eval]
  | neg φ ih =>
    constructor
    · intro h
      simp only [PropForm.eval] at h
      rw [hNeg φ]
      intro hφ
      simp [ih.mpr hφ] at h
    · intro h
      rw [hNeg φ] at h
      simp only [PropForm.eval]
      cases hb : PropForm.eval (fun a => decide (PropForm.atom a ∈ M)) φ
      · simp
      · exact absurd (ih.mp hb) h
  | conj φ ψ ih1 ih2 =>
    simp only [PropForm.eval, Bool.and_eq_true, ih1, ih2]
    exact (hConj φ ψ).symm

end Problems.compactness

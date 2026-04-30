import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s11_sub_1
import Problems.compactness.proofs.L_s11_sub_2

namespace Problems.compactness

open Classical

theorem s11 {α : Type} (M : Set (PropForm α))
    (hNeg  : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M)) :
    ∃ v : Valuation α, ∀ φ : PropForm α, φ ∈ M → PropForm.eval v φ = true := by
  obtain ⟨v, hv⟩ := s11_sub_1 M
  have hbidi : ∀ φ : PropForm α, PropForm.eval v φ = true ↔ φ ∈ M :=
    s11_sub_2 M hNeg hConj v hv
  exact ⟨v, fun φ hφ => (hbidi φ).mpr hφ⟩

end Problems.compactness

import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s15_sub_1
import Problems.compactness.proofs.L_s15_sub_2
import Problems.compactness.proofs.L_s15_sub_3

namespace Problems.compactness

open Classical

theorem s15 {α : Type} (M : Set (PropForm α))
    (hNeg  : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M)) :
    ∃ v : Valuation α, ∀ φ : PropForm α, φ ∈ M → PropForm.eval v φ = true := by
  have hIff : ∀ φ : PropForm α,
      PropForm.eval (fun a => decide (PropForm.atom a ∈ M)) φ = true ↔ φ ∈ M :=
    s15_sub_3 M hNeg hConj
  exact ⟨fun a => decide (PropForm.atom a ∈ M), fun φ hφ => (hIff φ).mpr hφ⟩

end Problems.compactness

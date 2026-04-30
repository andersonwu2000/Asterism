import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s14_sub_1
import Problems.compactness.proofs.L_s14_sub_2
import Problems.compactness.proofs.L_s14_sub_3

namespace Problems.compactness

open Classical

theorem s14 {α : Type} (M : Set (PropForm α))
    (hNeg  : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M)) :
    ∃ v : Valuation α, ∀ φ : PropForm α, φ ∈ M → PropForm.eval v φ = true := by
  let v : Valuation α := fun a => decide (PropForm.atom a ∈ M)
  have key : ∀ φ : PropForm α, φ ∈ M ↔ PropForm.eval v φ = true := fun φ => by
    induction φ with
    | atom a    => exact s14_sub_1 M a
    | neg φ ih  => exact s14_sub_2 M hNeg v φ ih
    | conj φ ψ ihφ ihψ => exact s14_sub_3 M hConj v φ ψ ihφ ihψ
  exact ⟨v, fun φ hφ => (key φ).mp hφ⟩

end Problems.compactness

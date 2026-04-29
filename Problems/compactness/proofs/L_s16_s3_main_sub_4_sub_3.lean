import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s16_s3_main_sub_4_sub_3 :
    ∀ {α : Type} (M : Set (PropForm α)) (v : Valuation α) (p : PropForm α),
    (∀ q : PropForm α, PropForm.neg q ∈ M ↔ q ∉ M) →
    (p ∈ M ↔ PropForm.eval v p = true) →
    (PropForm.neg p ∈ M ↔ PropForm.eval v (PropForm.neg p) = true) := by
  intro α M v p h_neg h_ih
  simp only [PropForm.eval]
  constructor
  · intro hmem
    have hnotp : p ∉ M := (h_neg p).mp hmem
    cases h : PropForm.eval v p with
    | true => exact absurd (h_ih.mpr h) hnotp
    | false => simp [h]
  · intro heval
    apply (h_neg p).mpr
    intro hp
    simp [h_ih.mp hp] at heval

end Problems.compactness

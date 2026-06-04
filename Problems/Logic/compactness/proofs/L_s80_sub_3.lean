import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s80_sub_3 : ∀ {α : Type} (M : Set (PropForm α)) (v : Valuation α),
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    ∀ p : PropForm α,
    (p ∈ M ↔ PropForm.eval v p = true) →
    (PropForm.neg p ∈ M ↔ PropForm.eval v (PropForm.neg p) = true) := by
  intro α M v hneg p ih
  constructor
  · intro h
    have hnotin : p ∉ M := (hneg p).mp h
    simp only [PropForm.eval]
    cases hb : PropForm.eval v p with
    | true  => exact absurd (ih.mpr hb) hnotin
    | false => rfl
  · intro h
    apply (hneg p).mpr
    intro hm
    simp [PropForm.eval, ih.mp hm] at h

end Problems.Logic.compactness

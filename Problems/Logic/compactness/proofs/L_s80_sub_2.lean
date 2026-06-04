import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s80_sub_2 : ∀ {α : Type} (M : Set (PropForm α)) (v : Valuation α),
    (∀ a : α, v a = true ↔ PropForm.atom a ∈ M) →
    ∀ a : α, PropForm.atom a ∈ M ↔ PropForm.eval v (PropForm.atom a) = true := by
  intro α M v hv a
  simp only [PropForm.eval]
  exact (hv a).symm

end Problems.Logic.compactness

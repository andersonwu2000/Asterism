import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s16_s3_main_sub_4_sub_2 :
    ∀ {α : Type} (M : Set (PropForm α)) (v : Valuation α),
    (∀ a : α, v a = true ↔ PropForm.atom a ∈ M) →
    ∀ a : α, PropForm.atom a ∈ M ↔ PropForm.eval v (PropForm.atom a) = true := by
  intro α M v h a
  simp only [PropForm.eval]
  exact (h a).symm

end Problems.compactness

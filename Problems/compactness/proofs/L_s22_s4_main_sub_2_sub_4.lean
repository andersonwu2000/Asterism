import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s22_s4_main_sub_2_sub_4 : ∀ {α : Type} (T : Set (PropForm α)) (p : PropForm α),
    ¬Sat (insert p T) →
    ∀ v : Valuation α,
    (∀ q ∈ T, PropForm.eval v q = true) →
    PropForm.eval v (PropForm.neg p) = true := by
  sorry

end Problems.compactness

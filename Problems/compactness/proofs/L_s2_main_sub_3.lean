import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Satisfiability is monotone: a subset of a satisfiable set is satisfiable.
theorem s2_main_sub_3 {α : Type} (S M : Set (PropForm α)) (hSM : S ⊆ M) (hM : Sat M) : Sat S := by sorry

end Problems.compactness

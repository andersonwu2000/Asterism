import Mathlib
import Problems.localization_euclidean.Defs

namespace Problems.localization_euclidean

theorem main : ∀ {D : Type*} [EuclideanDomain D] (S : Submonoid D),
    0 ∉ S → Nonempty (EuclideanDomain (Localization S)) := by sorry

end Problems.localization_euclidean

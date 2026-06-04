import Mathlib
import Problems.Algebra.localization_euclidean.Defs

namespace Problems.Algebra.localization_euclidean

theorem main : ∀ {D : Type*} [EuclideanDomain D] (S : Submonoid D),
    0 ∉ S → Nonempty (EuclideanDomain (Localization S)) := by sorry

end Problems.Algebra.localization_euclidean
